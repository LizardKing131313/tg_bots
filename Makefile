include makefiles/common.mk
include makefiles/setup.mk
include makefiles/i18n.mk
include makefiles/dev.mk

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  help-setup, help-i18n, help-dev"
	@echo "  venv, upgrade-pip, pip-tools, setup, hooks"
	@echo "  compile, compile-dev, compile-full, compile-all, compile-every, compile-update"
	@echo "  sync, sync-dev, sync-full, sync-all"
	@echo "  compile-locales, compile-locale"
	@echo "  lint, format, typecheck, test, test-all, coverage, coverage-badge, ci"
