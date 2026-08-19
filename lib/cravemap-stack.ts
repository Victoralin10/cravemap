import * as cdk from 'aws-cdk-lib/core';
import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import * as apigwint from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import { Construct } from 'constructs';

export class CravemapStack extends cdk.Stack {
  public readonly dishesTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.dishesTable = new dynamodb.Table(this, 'Dishes', {
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // El agente Strands vive en un Lambda de contenedor: AgentCore Runtime tiene
    // cuota 0 en esta cuenta (Total Agents per Account = 0), y Strands es solo una libreria.
    const agent = new lambda.DockerImageFunction(this, 'Agent', {
      code: lambda.DockerImageCode.fromImageAsset('agent'),
      architecture: lambda.Architecture.ARM_64,
      memorySize: 1024,
      timeout: cdk.Duration.seconds(60),
      environment: { TABLE_NAME: this.dishesTable.tableName, MODEL_ID: 'google.gemma-4-31b' },
    });
    this.dishesTable.grantReadData(agent);
    // bedrock-mantle:CreateInference + CallWithBearerToken; Strands autentica con bearer acunado.
    agent.role!.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonBedrockMantleInferenceAccess'),
    );

    // El stage se llama "api" para que absorba el prefijo del path: CloudFront reenvia
    // /api/craving tal cual y API Gateway lo lee como stage=api + ruta /craving.
    const api = new apigw.HttpApi(this, 'AgentApi', { createDefaultStage: false });
    api.addRoutes({
      path: '/craving',
      methods: [apigw.HttpMethod.POST],
      integration: new apigwint.HttpLambdaIntegration('AgentIntegration', agent),
    });
    const stage = new apigw.HttpStage(this, 'ApiStage', { httpApi: api, stageName: 'api', autoDeploy: true });

    const siteBucket = new s3.Bucket(this, 'SiteBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const distribution = new cloudfront.Distribution(this, 'SiteDistribution', {
      defaultRootObject: 'index.html',
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(siteBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      },
      additionalBehaviors: {
        '/api/*': {
          origin: new origins.HttpOrigin(`${api.apiId}.execute-api.${this.region}.amazonaws.com`),
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          // Host no: execute-api exige su propio Host para resolver el stage.
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        },
      },
      // Sin errorResponses: son a nivel distribucion y enmascaraban los errores de /api/*
      // como index.html con 200. El front es un solo archivo, no necesita rewrite de rutas.
    });

    new s3deploy.BucketDeployment(this, 'SiteDeployment', {
      sources: [s3deploy.Source.asset('web')],
      destinationBucket: siteBucket,
      distribution,
      distributionPaths: ['/*'],
    });

    new cdk.CfnOutput(this, 'DishesTableName', { value: this.dishesTable.tableName });
    new cdk.CfnOutput(this, 'SiteBucketName', { value: siteBucket.bucketName });
    new cdk.CfnOutput(this, 'DistributionId', { value: distribution.distributionId });
    new cdk.CfnOutput(this, 'SiteUrl', { value: `https://${distribution.domainName}` });
    new cdk.CfnOutput(this, 'ApiUrl', { value: stage.url });
    new cdk.CfnOutput(this, 'AgentFunctionName', { value: agent.functionName });
  }
}
