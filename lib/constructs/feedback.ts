import * as fs from 'node:fs';
import * as cdk from 'aws-cdk-lib/core';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';
import { MODEL_ID } from './compute';

export interface FeedbackProps {
  dishesTable: dynamodb.ITable;
  /** El mismo asset del agente (Compute.code): mismo zip, distinto handler. */
  agentCode: lambda.Code;
}

export class Feedback extends Construct {
  readonly table: dynamodb.Table;
  readonly fn: lambda.Function;
  readonly curator: lambda.Function;

  constructor(scope: Construct, id: string, props: FeedbackProps) {
    super(scope, id);

    this.table = new dynamodb.Table(this, 'Table', {
      // local = "{distrito}#{osm_id}" agrupa por restaurante, que es como el curador
      // procesa: un local por vez. ts = ISO8601 + sufijo random para que dos reportes
      // del mismo segundo no se pisen.
      partitionKey: { name: 'local', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'ts', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Los ids del catalogo van por env en vez de una tercera copia de platos.json:
    // ~450 bytes y la lambda de ingesta se queda sin bundling (solo boto3 del runtime).
    const platos: string = (
      JSON.parse(fs.readFileSync('agent/platos.json', 'utf8')) as { id: string }[]
    )
      .map((p) => p.id)
      .join(',');

    this.fn = new lambda.Function(this, 'Ingest', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'feedback.handler',
      code: lambda.Code.fromAsset('lambdas', { exclude: ['test_*.py', '__pycache__'] }),
      architecture: lambda.Architecture.ARM_64,
      timeout: cdk.Duration.seconds(10),
      environment: { FEEDBACK_TABLE: this.table.tableName, PLATOS_IDS: platos },
    });
    // Endpoint publico: PutItem y nada mas. grantWriteData daria tambien DeleteItem,
    // que esta lambda no usa y nadie deberia poder alcanzar desde internet.
    this.table.grant(this.fn, 'dynamodb:PutItem');

    this.curator = new lambda.Function(this, 'Curator', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'curador.handler',
      code: props.agentCode,
      architecture: lambda.Architecture.ARM_64,
      memorySize: 1024,
      timeout: cdk.Duration.minutes(5),
      environment: {
        TABLE_NAME: props.dishesTable.tableName,
        FEEDBACK_TABLE: this.table.tableName,
        MODEL_ID,
      },
    });
    this.table.grantReadWriteData(this.curator);
    props.dishesTable.grantReadWriteData(this.curator);
    this.curator.role!.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonBedrockMantleInferenceAccess'),
    );

    // 08:00 UTC = 3:00 am en Lima (UTC-5, sin horario de verano). Un cron y un scan:
    // a esta escala no hace falta ni cola ni stream.
    new events.Rule(this, 'Nightly', {
      schedule: events.Schedule.cron({ minute: '0', hour: '8' }),
      targets: [new targets.LambdaFunction(this.curator)],
    });
  }
}
