import * as cdk from 'aws-cdk-lib/core';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

export interface ComputeProps {
  table: dynamodb.ITable;
}

export class Compute extends Construct {
  readonly fn: lambda.DockerImageFunction;

  constructor(scope: Construct, id: string, props: ComputeProps) {
    super(scope, id);

    // El agente Strands vive en un Lambda de contenedor: AgentCore Runtime tiene
    // cuota 0 en esta cuenta (Total Agents per Account = 0), y Strands es solo una libreria.
    this.fn = new lambda.DockerImageFunction(this, 'Agent', {
      code: lambda.DockerImageCode.fromImageAsset('agent'),
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
