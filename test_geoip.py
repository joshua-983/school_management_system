import geoip2.database

def test_database():
    db_path = '/mnt/e/projects/school/data/geoip/GeoLite2-City/GeoLite2-City.mmdb'
    try:
        print("\nTesting GeoIP database...")
        with geoip2.database.Reader(db_path) as reader:
            # Test with Google's IP
            response = reader.city('8.8.8.8')
            print(f"Country: {response.country.name}")
            print(f"City: {response.city.name if response.city.name else 'N/A'}")
            print(f"Coordinates: {response.location.latitude}, {response.location.longitude}")
        print("Test successful!")
        return True
    except Exception as e:
        print(f"\nError testing database: {str(e)}")
        return False

if __name__ == '__main__':
    test_database()
