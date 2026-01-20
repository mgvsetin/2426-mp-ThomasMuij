from uuid import UUID

def convert_uuids_to_str(obj):
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, dict):
        return {k: convert_uuids_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_uuids_to_str(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(convert_uuids_to_str(v) for v in obj)
    return obj