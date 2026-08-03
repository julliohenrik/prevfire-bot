import cv2
import os

# ============================
# CONFIGURAÇÕES
# ============================

video = input("Digite o caminho do vídeo (.mov): ")

saida = input("Digite a pasta onde deseja salvar as imagens: ")

intervalo = int(input("Salvar um frame a cada quantos frames? "))

# ============================
# CRIA A PASTA SE NÃO EXISTIR
# ============================

if not os.path.exists(saida):
    os.makedirs(saida)

# ============================
# ABRE O VÍDEO
# ============================

cap = cv2.VideoCapture(video)

if not cap.isOpened():
    print("Erro ao abrir o vídeo.")
    exit()

contador_frame = 0
contador_imagem = 0

print("Extraindo frames...")

while True:

    ret, frame = cap.read()

    if not ret:
        break

    if contador_frame % intervalo == 0:

        nome = os.path.join(
            saida,
            f"frame_{contador_imagem:06d}.jpg"
        )

        cv2.imwrite(nome, frame)
        contador_imagem += 1

    contador_frame += 1

cap.release()

print("\nConcluído!")
print(f"Frames lidos: {contador_frame}")
print(f"Imagens salvas: {contador_imagem}")
