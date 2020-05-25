FROM python:3.7-buster
WORKDIR /usr/src/app
COPY ./rpn.py /usr/local/bin/rpn
RUN chown 755 /usr/local/bin/rpn
CMD rpn