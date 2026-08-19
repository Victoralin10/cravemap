import * as cdk from 'aws-cdk-lib/core';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';
import { Api } from './constructs/api';
import { Compute } from './constructs/compute';
import { Database } from './constructs/database';
import { Frontend } from './constructs/frontend';

export class CravemapStack extends cdk.Stack {
  public readonly dishesTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const database = new Database(this, 'Database');
    const compute = new Compute(this, 'Compute', { table: database.table });
    const api = new Api(this, 'Api', { fn: compute.fn });
    const frontend = new Frontend(this, 'Frontend', { apiId: api.apiId, assetPath: 'web/dist' });

    this.dishesTable = database.table;

    new cdk.CfnOutput(this, 'DishesTableName', { value: database.table.tableName });
    new cdk.CfnOutput(this, 'SiteBucketName', { value: frontend.bucket.bucketName });
    new cdk.CfnOutput(this, 'DistributionId', { value: frontend.distribution.distributionId });
    new cdk.CfnOutput(this, 'SiteUrl', { value: `https://${frontend.distribution.domainName}` });
    new cdk.CfnOutput(this, 'ApiUrl', { value: api.url });
    new cdk.CfnOutput(this, 'AgentFunctionName', { value: compute.fn.functionName });
  }
}
