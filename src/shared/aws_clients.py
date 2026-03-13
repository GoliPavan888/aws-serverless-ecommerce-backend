import boto3

from shared.config import AWS_ENDPOINT_URL, AWS_REGION


_session = boto3.session.Session()


def sqs_client():
    return _session.client("sqs", region_name=AWS_REGION, endpoint_url=AWS_ENDPOINT_URL)


def sns_client():
    return _session.client("sns", region_name=AWS_REGION, endpoint_url=AWS_ENDPOINT_URL)


def lambda_client():
    return _session.client("lambda", region_name=AWS_REGION, endpoint_url=AWS_ENDPOINT_URL)


def apigw_client():
    return _session.client("apigateway", region_name=AWS_REGION, endpoint_url=AWS_ENDPOINT_URL)
