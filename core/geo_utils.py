import geoip2.database
from django.conf import settings
from django.core.cache import cache

def get_location_info(ip_address: str) -> dict:
    cache_key = f'geoip_{ip_address}'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return cached_data
    
    try:
        with geoip2.database.Reader(f'{settings.GEOIP_PATH}/{settings.GEOIP_CITY}') as reader:
            response = reader.city(ip_address)
            location_data = {
                'city': response.city.name,
                'country': response.country.name,
                'iso_code': response.country.iso_code,
                'latitude': response.location.latitude,
                'longitude': response.location.longitude,
                'timezone': response.location.time_zone,
            }
            cache.set(cache_key, location_data, timeout=86400)  # Cache for 1 day
            return location_data
    except Exception as e:
        return {
            'error': str(e),
            'ip': ip_address
        }

# Add to your existing log_audit function:
# location = get_location_info(request.META.get('REMOTE_ADDR'))
# audit_log.location_data = location