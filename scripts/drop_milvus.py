from pymilvus import MilvusClient

client = MilvusClient(uri="http://127.0.0.1:19530")

if client.has_collection("medical_chunks"):
    client.drop_collection("medical_chunks")
    print("已删除旧集合 medical_chunks")
else:
    print("集合不存在，无需删除")
