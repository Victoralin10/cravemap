import * as cdk from 'aws-cdk-lib/core';
import * as agentcore from 'aws-cdk-lib/aws-bedrockagentcore';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as ecrAssets from 'aws-cdk-lib/aws-ecr-assets';
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

    // El agente Strands corre en AgentCore Runtime: contenedor ARM64, HTTP en :8080.
    const agent = new agentcore.Runtime(this, 'Agent', {
      runtimeName: 'cravemap_agent',
      agentRuntimeArtifact: agentcore.AgentRuntimeArtifact.fromAsset('agent', {
        platform: ecrAssets.Platform.LINUX_ARM64,
      }),
      environmentVariables: { TABLE_NAME: this.dishesTable.tableName },
    });
    this.dishesTable.grantReadData(agent.role);
    // bedrock-mantle:CreateInference + CallWithBearerToken; Strands autentica con bearer acunado.
    agent.role.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonBedrockMantleInferenceAccess'),
    );

    // El navegador no puede firmar SigV4, asi que este proxy es quien invoca al runtime.
    const proxy = new lambda.Function(this, 'Proxy', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'proxy.handler',
      code: lambda.Code.fromAsset('lambda'),
      timeout: cdk.Duration.seconds(60),
      environment: { AGENT_RUNTIME_ARN: agent.agentRuntimeArn },
    });
    agent.grantInvoke(proxy);

    const proxyUrl = proxy.addFunctionUrl({ authType: lambda.FunctionUrlAuthType.AWS_IAM });

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
          origin: origins.FunctionUrlOrigin.withOriginAccessControl(proxyUrl),
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        },
      },
      errorResponses: [403, 404].map((httpStatus) => ({
        httpStatus,
        responseHttpStatus: 200,
        responsePagePath: '/index.html',
      })),
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
    new cdk.CfnOutput(this, 'AgentRuntimeArn', { value: agent.agentRuntimeArn });
  }
}
