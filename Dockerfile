FROM python:3.12-slim

RUN pip install pipenv

ENV PROJECT_DIR /app

WORKDIR ${PROJECT_DIR}

COPY Pipfile Pipfile.lock ${PROJECT_DIR}/

RUN pipenv install --system --deploy

COPY cat_watcher cat_watcher
COPY settings.ini cat_watcher/settings.ini

ENV SEND_MESSAGES True

CMD python3 -m cat_watcher.cat_watcher
