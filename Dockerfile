# Dockerfile
FROM python:3.8-slim-buster

WORKDIR /app

COPY . .
RUN pip install -U certifi
RUN pip install -e .[dev]


# make alias to run it as amcat4 instaed of /srv/amcat/env/bin/python -m amcat4
RUN echo '#!/bin/bash\npython -m amcat4 "$@"' > /usr/bin/amcat4 && \
    chmod +x /usr/bin/amcat4

EXPOSE 5000

CMD ["amcat4", "run"]
