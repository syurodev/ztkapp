from app.schemas.create_user import schema as create_user_schema
from app.schemas.delete_user import schema as delete_user_schema
from app.schemas.get_fingerprint import schema as get_fingerprint_schema
from app.schemas.delete_fingerprint import schema as delete_fingerprint_schema

def validate_data(data, schema):
    """Simple validation function"""
    from jsonschema import validate as jsonschema_validate
    from jsonschema.exceptions import ValidationError
    try:
        jsonschema_validate(instance=data, schema=schema)
        return True, None
    except ValidationError as e:
        return False, str(e)

__all__ = [
    'create_user_schema',
    'delete_user_schema',
    'get_fingerprint_schema',
    'delete_fingerprint_schema',
    'validate_data',
]
