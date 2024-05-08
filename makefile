BUMP = patch # major, minor, patch

# Bump the version of the package
version-bump:
	@poetry version $(BUMP)

# Create a release on github with wheel
release: version-bump
	$(eval VERSION := $(shell poetry version -s))
	@echo Building version: $(VERSION)
	@poetry build
	@git add pyproject.toml
	@git commit -m "Release version $(VERSION)"
	@git tag v$(VERSION)
	@git push origin main
	@git push --tags

# Publish the package on pypi
publish: release
	@poetry publish
