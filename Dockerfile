FROM ubuntu:14.04

WORKDIR /app

RUN apt-get update -qq && apt-get install -y \
	python-dev \
	python-pip

RUN apt-get autoclean && apt-get clean && apt-get autoremove

ADD requirements.txt /app/requirements.txt

RUN pip install -r requirements.txt

ADD . /app/

EXPOSE 5000

CMD ["python", "app.py"]

