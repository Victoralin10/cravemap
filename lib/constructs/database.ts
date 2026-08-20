import * as cdk from 'aws-cdk-lib/core';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';

export class Database extends Construct {
  readonly table: dynamodb.Table;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.table = new dynamodb.Table(this, 'Table', {
      // plato = id del catalogo, local = "{distrito}#{osm_id}": query por plato y
      // begins_with por distrito, sin scan y sin GSI.
      partitionKey: { name: 'plato', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'local', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
  }
}
