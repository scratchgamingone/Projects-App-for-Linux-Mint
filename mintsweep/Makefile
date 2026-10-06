.PHONY: all run deb clean

all: deb

run:
	./bin/mintsweep

deb:
	./build-deb.sh

clean:
	rm -rf build mintsweep_*.deb
	find . -type d -name "__pycache__" -exec rm -rf {} +
