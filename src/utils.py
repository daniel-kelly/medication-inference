def get_field(entry, field):
    """
    Returns the value of a field from the main entry or from 'openfda'.
    If the value is a non-empty list, returns the first item.
    Otherwise returns the string value if present.
    """
    value = entry.get(field)

    if value is None and "openfda" in entry:
        value = entry["openfda"].get(field)

    if isinstance(value, list):
        value = value[0]

    # If value is not None (i.e. is str) then upper for consistent formatting
    value = value.upper() if isinstance(value, str) else value

    return value

def get_first_available_field(entry, fields, default="[Unknown]"):
    """
    Returns the first available value from a list of possible field names,
    using get_field() to look in both top-level and `openfda`.
    """
    for field in fields:
        val = get_field(entry, field)
        if val is not None:
            return val
    return default

