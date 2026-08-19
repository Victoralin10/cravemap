#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib/core';
import { CravemapStack } from '../lib/cravemap-stack';

const app = new cdk.App();
new CravemapStack(app, 'CravemapStack', {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION },
});
