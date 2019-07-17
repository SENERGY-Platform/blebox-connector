FROM python:3-alpine

WORKDIR /usr/src/app

RUN apk update && apk upgrade && apk add --no-cache git

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir cc-lib
RUN touch blebox.conf
RUN touch devices.sqllite3

CMD [ "python", "./client.py"]
