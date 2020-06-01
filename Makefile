PWD := $(shell pwd)

.PHONY: test
test: test3.6 test3.7 test3.8

test3.6:
	docker run -w /app -v $(PWD):/app python:3.6.10-alpine3.11 python -m unittest
test3.7:
	docker run -w /app -v $(PWD):/app python:3.7.7-alpine3.11 python -m unittest
test3.8:
	docker run -w /app -v $(PWD):/app python:3.8.3-alpine3.11 python -m unittest

