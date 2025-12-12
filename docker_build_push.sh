#! /bin/bash

IMAGE_NAME=groq_chat
USER=fabrikant


SERVER=ghcr.io

# Формируем дополнительный тэг на основе текущей даты и времени
DATE_TAG=$(date +%Y.%m.%d.%H%M%S)

IMAGE_LATEST_TAG=$SERVER/$USER/$IMAGE_NAME:latest
IMAGE_DATE_TAG=$SERVER/$USER/$IMAGE_NAME:$DATE_TAG

# Флаг для пропуска push
SKIP_PUSH=false

# Функция для вывода справки
show_help() {
	echo "Скрипт для сборки и отправки Docker-образа в Container Registry."
	echo "Использование: ./docker_build_push.sh [ОПЦИИ]"
	echo ""
	echo "Опции:"
	echo "  --no-push   Только сборка образа, без отправки в репозиторий."
	echo "  -h, --help  Показать это справочное сообщение и выйти."
	echo ""
	echo "Пример использования:"
	echo "  ./docker_build_push.sh              # Сборка и отправка образа (latest и с датой)"
	echo "  ./docker_build_push.sh --no-push    # Только сборка образа (latest и с датой)"
}

# Обработка аргументов командной строки
for arg in "$@"; do
	case $arg in
	--no-push)
		SKIP_PUSH=true
		shift # Удаляем аргумент после обработки
		;;
	-h | --help)
		show_help
		exit 0 # Выходим после показа справки
		;;
	*)
		# Неизвестный аргумент, можно добавить обработку ошибок или игнорировать
		echo "Неизвестный аргумент: $arg"
		show_help
		exit 1
		;;
	esac
done

echo "Building image..."
# Добавляем оба тэга к образу
docker build -t $IMAGE_LATEST_TAG -t $IMAGE_DATE_TAG .
echo "Build complete"

if [ "$SKIP_PUSH" = false ]; then
	echo "Pushing to registry..."
	# Отправляем оба тэга в репозиторий
	docker push $IMAGE_LATEST_TAG
	docker push $IMAGE_DATE_TAG
	echo "Push complete"

	docker image rm -f $IMAGE_LATEST_TAG $IMAGE_DATE_TAG
	echo "Образы удалены после выгрузки в репозиторий"

else
	echo "Push to registry skipped (--no-push flag was used)."
fi

docker image prune -f

echo ""
echo "Image names:"
echo $IMAGE_LATEST_TAG
echo $IMAGE_DATE_TAG
