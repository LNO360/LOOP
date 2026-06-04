import boto3
from botocore.exceptions import ClientError
from core.config import settings

def _get_s3():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )

async def upload_file_to_s3(key: str, content: bytes, content_type: str) -> str:
    s3 = _get_s3()
    try:
        s3.create_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        pass
    s3.put_object(Bucket=settings.s3_bucket, Key=key, Body=content, ContentType=content_type)
    return f"{settings.s3_endpoint}/{settings.s3_bucket}/{key}"
