import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import * as apigwint from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

export interface ApiProps {
  fn: lambda.IFunction;
  feedbackFn: lambda.IFunction;
}

export class Api extends Construct {
  readonly apiId: string;
  readonly stage: apigw.HttpStage;
  readonly url: string;

  constructor(scope: Construct, id: string, props: ApiProps) {
    super(scope, id);

    // El stage se llama "api" para que absorba el prefijo del path: CloudFront reenvia
    // /api/craving tal cual y API Gateway lo lee como stage=api + ruta /craving.
    const api = new apigw.HttpApi(this, 'AgentApi', { createDefaultStage: false });
    api.addRoutes({
      path: '/craving',
      methods: [apigw.HttpMethod.POST],
      integration: new apigwint.HttpLambdaIntegration('AgentIntegration', props.fn),
    });
    api.addRoutes({
      path: '/feedback',
      methods: [apigw.HttpMethod.POST],
      integration: new apigwint.HttpLambdaIntegration('FeedbackIntegration', props.feedbackFn),
    });
    this.stage = new apigw.HttpStage(this, 'Stage', {
      httpApi: api,
      stageName: 'api',
      autoDeploy: true,
      // /feedback es escritura publica y sin auth: el techo esta para que una tarde
      // tonta (o un bucle de alguien) no se convierta en factura.
      throttle: { rateLimit: 20, burstLimit: 40 },
    });

    this.apiId = api.apiId;
    this.url = this.stage.url;
  }
}
