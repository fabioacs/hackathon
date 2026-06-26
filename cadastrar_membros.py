"""
============================================================
CADASTRO EM MASSA DE MEMBROS NO SUPABASE
============================================================

O que este script faz:
1. Lê o CSV exportado da planilha SECUNDÁRIA de membros do Fillout
   (a que tem um membro por linha, com e-mail e nome).
2. Gera uma senha inicial para cada membro, derivada dos próprios
   dados (nome + parte de outro campo, conforme você definir abaixo).
3. Cria o usuário no Supabase com e-mail + senha gerada.
4. Salva um novo CSV com e-mail e senha de cada membro, para você
   usar como base do envio de e-mail via Fillout.

------------------------------------------------------------
ANTES DE RODAR:
------------------------------------------------------------
1. Instale a biblioteca necessária:
   pip install supabase --break-system-packages

2. Preencha as variáveis abaixo:
   - SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY
     (a service_role key, NÃO a anon key — ela fica em
     Project Settings > API > service_role. Essa chave é
     SECRETA, nunca a coloque em páginas HTML públicas.
     Use-a apenas aqui, neste script, rodado localmente.)

3. Ajuste os nomes das colunas do seu CSV nas variáveis
   COLUNA_EMAIL, COLUNA_NOME e COLUNA_EQUIPE mais abaixo,
   para bater com os nomes exatos das colunas exportadas
   do Fillout.

4. Ajuste a função gerar_senha() com a fórmula que vocês
   combinaram (ex: primeiro nome + 4 últimos dígitos do
   telefone, primeiro nome + ano de nascimento, etc.)
------------------------------------------------------------
"""

import csv
import re
import unicodedata
from supabase import create_client, Client

# ============================================================
# CONFIGURAÇÃO — edite estes valores
# ============================================================

SUPABASE_URL = "https://racwxzwfyssyvirswsaf.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJhY3d4endmeXNzeXZpcnN3c2FmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MTcyMTAxMSwiZXhwIjoyMDk3Mjk3MDExfQ.umJDX73-GrDRZ4NvSA6YU0oCFCvpPgd1AjBJPVahWpU"

ARQUIVO_CSV_ENTRADA = "membros.csv"        # CSV exportado do Fillout
ARQUIVO_CSV_SAIDA = "membros_com_senha.csv"  # CSV gerado com e-mail + senha

# Nomes EXATOS das colunas no seu CSV exportado do Fillout.
# Abra o CSV e confira os cabeçalhos para ajustar se necessário.
COLUNA_EMAIL = "E-mail"
COLUNA_NOME = "Nome Completo"
COLUNA_EQUIPE = "Equipe"

# Campo extra usado para compor a senha: aqui usamos o RA (Registro Acadêmico).
COLUNA_EXTRA_PARA_SENHA = "RA"


def gerar_senha(nome: str, valor_extra: str) -> str:
    """
    Gera uma senha inicial a partir do nome e do RA.

    Fórmula: 3 primeiras letras do primeiro nome (sem acento, minúsculo)
    + 4 primeiros dígitos do RA.
    Resultado: "joa4521"
    """
    primeiro_nome = nome.strip().split(" ")[0]
    primeiro_nome = unicodedata.normalize("NFKD", primeiro_nome)
    primeiro_nome = primeiro_nome.encode("ascii", "ignore").decode("utf-8").lower()
    tres_letras = primeiro_nome[:3]

    apenas_numeros = re.sub(r"\D", "", valor_extra or "")
    prefixo_ra = apenas_numeros[:4] if len(apenas_numeros) >= 4 else apenas_numeros

    return f"{tres_letras}{prefixo_ra}"


def main():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    linhas_saida = []
    total_novos = 0
    total_ja_existiam = 0

    with open(ARQUIVO_CSV_ENTRADA, newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)

        for linha in leitor:
            email = linha.get(COLUNA_EMAIL, "").strip()
            nome = linha.get(COLUNA_NOME, "").strip()
            equipe = linha.get(COLUNA_EQUIPE, "").strip()
            valor_extra = linha.get(COLUNA_EXTRA_PARA_SENHA, "") if COLUNA_EXTRA_PARA_SENHA else ""

            if not email:
                print(f"[AVISO] Linha sem e-mail, pulando: {linha}")
                continue

            senha = gerar_senha(nome, valor_extra)

            try:
                resposta = supabase.auth.admin.create_user({
                    "email": email,
                    "password": senha,
                    "email_confirm": True,  # já marca o e-mail como confirmado
                    "user_metadata": {
                        "nome": nome,
                        "equipe": equipe,
                        # Marca que esta pessoa ainda precisa trocar a senha
                        # temporária no primeiro acesso. A página de login
                        # confere esse campo e força a troca antes de liberar
                        # a área exclusiva.
                        "precisa_trocar_senha": True,
                    },
                })
                print(f"[OK] Usuário criado: {email}")
                total_novos += 1
            except Exception as erro:
                mensagem_erro = str(erro)
                if "already been registered" in mensagem_erro or "already registered" in mensagem_erro:
                    # Pessoa já cadastrada em uma execução anterior do script.
                    # Isso é esperado quando o script roda periodicamente
                    # conforme novas equipes se inscrevem — não é um problema.
                    print(f"[JÁ EXISTE] {email} já estava cadastrado, pulando.")
                    total_ja_existiam += 1
                else:
                    print(f"[ERRO] Falha ao criar {email}: {erro}")
                continue

            linhas_saida.append({
                "Nome": nome,
                "Email": email,
                "Equipe": equipe,
                "Senha": senha,
            })

    with open(ARQUIVO_CSV_SAIDA, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=["Nome", "Email", "Equipe", "Senha"])
        escritor.writeheader()
        escritor.writerows(linhas_saida)

    print(f"\nConcluído.")
    print(f"  Novos usuários criados: {total_novos}")
    print(f"  Já existiam (pulados):  {total_ja_existiam}")
    print(f"\nArquivo gerado: {ARQUIVO_CSV_SAIDA}")
    print("(contém apenas os usuários NOVOS criados nesta execução — use-o")
    print("para disparar o e-mail só para quem ainda não recebeu login)")


if __name__ == "__main__":
    main()
