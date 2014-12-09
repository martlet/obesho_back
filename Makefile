default:
	@echo There is no default action!

req:
	@pip3.4 install -r requirements.txt

lint:
	-@pylint --rcfile=.pylintrc obesho_back.py db_schema.py db_fill.py

server:
	python3.4 obesho_back.py

db_schema:
	python3.4 db_schema.py

db_fill:
	python3.4 db_fill.py

build:
	@python3.4 setup.py build

.PHONY: default req lint build
