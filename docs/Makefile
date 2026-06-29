.PHONY: help build clean serve

help:
	@echo "Prete-a-porter Documentation"
	@echo ""
	@echo "Available commands:"
	@echo "  make build    - Build HTML documentation"
	@echo "  make clean    - Clean build artifacts"
	@echo "  make serve    - Build and serve documentation locally"
	@echo "  make watch    - Watch for changes and rebuild"

build:
	@echo "Building documentation..."
	python3 -m sphinx -W -b html . _build/html
	@echo "Build complete! Open _build/html/index.html"

clean:
	@echo "Cleaning build artifacts..."
	rm -rf _build/
	@echo "Clean complete!"

serve: build
	@echo "Serving documentation at http://localhost:8080"
	cd _build/html && python3 -m http.server 8080

watch:
	@echo "Watching for changes (Ctrl+C to stop)..."
	@while true; do \
		inotifywait -e modify -r . --include '\.(rst|py)$$' && make build; \
	done
