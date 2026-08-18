from openai import OpenAI

# 这里的横杠全部是键盘英文减号，不要复制旧的key
client = OpenAI(
    api_key="sk-df59d4d083534657acf6bbce369e01dc",
    base_url="https://api.deepseek.com/v1"
)

resp = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role":"user","content":"hello"}]
)
print(resp.choices[0].message.content)