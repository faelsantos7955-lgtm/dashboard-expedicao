"""
gerar_senha.py — Gera o hash bcrypt para colocar no config.yaml

Uso:
    python gerar_senha.py
"""
import bcrypt

usuarios = {
    "admin":       "admin123",
    "sup_capital": "capital123",
    "sup_metro":   "metro123",
    "sup_country": "country123",
    "sup_geral":   "geral123",
}

print("=" * 60)
print("Cole os hashes abaixo no config.yaml")
print("=" * 60)
for usuario, senha in usuarios.items():
    h = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
    print(f"\n{usuario}:")
    print(f"  senha atual : {senha}")
    print(f"  hash        : {h}")

print("\n" + "=" * 60)
print("ATENÇÃO: troque as senhas antes de publicar!")
print("=" * 60)
