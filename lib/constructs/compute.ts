import * as cdk from 'aws-cdk-lib/core';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

export interface ComputeProps {
  table: dynamodb.ITable;
}

export class Compute extends Construct {
  readonly fn: lambda.Function;

  constructor(scope: Construct, id: string, props: ComputeProps) {
    super(scope, id);

    // El agente Strands vive en un Lambda normal: AgentCore Runtime tiene cuota 0 en esta
    // cuenta (Total Agents per Account = 0), y Strands es solo una libreria de Python puro.
    // agent/platos.json es copia de seed/platos.json: el asset es agent/, no alcanza a seed/.
    // Refrescala con: cp seed/platos.json agent/platos.json  (antes de cdk deploy)
    this.fn = new lambda.Function(this, 'Agent', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'handler.handler',
      code: lambda.Code.fromAsset('agent', {
        exclude: ['test_*.py', '__pycache__', '.venv'],
        bundling: {
          image: lambda.Runtime.PYTHON_3_13.bundlingImage,
          command: [
            'bash',
            '-c',
            'pip install -r requirements.txt -t /asset-output && cp *.py platos.json /asset-output && rm /asset-output/test_*.py' +
              // strands arrastra boto3/botocore como dependencia transitiva y son ~90 de los
              // 106 MB del asset. El runtime de Lambda ya los trae, asi que fuera del zip.
              ' && rm -rf /asset-output/boto3 /asset-output/botocore',
          ],
        },
      }),
      architecture: lambda.Architecture.ARM_64,
      memorySize: 1024,
      timeout: cdk.Duration.seconds(60),
      environment: { TABLE_NAME: props.table.tableName, MODEL_ID: 'google.gemma-4-31b' },
    });
    props.table.grantReadData(this.fn);
    // bedrock-mantle:CreateInference + CallWithBearerToken; Strands autentica con bearer acunado.
    this.fn.role!.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonBedrockMantleInferenceAccess'),
    );
  }
}
