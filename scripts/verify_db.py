import os
from supabase import create_client
from qdrant_client import QdrantClient
from dotenv import load_dotenv

load_dotenv()

print('SUPABASE (Primary):')
print('-' * 40)
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

for table in ['product_listings', 'service_listings', 'mutual_listings', 'matches']:
    result = client.table(table).select('*').execute()
    print(f'  {table}: {len(result.data)} rows')

print()
print('QDRANT (Primary):')
print('-' * 40)
qdrant = QdrantClient(url=os.getenv('QDRANT_ENDPOINT'), api_key=os.getenv('QDRANT_API_KEY'))

for coll in ['product_vectors', 'service_vectors', 'mutual_vectors']:
    info = qdrant.get_collection(coll)
    print(f'  {coll}: {info.points_count} points')

print()
print('All data verified!')
