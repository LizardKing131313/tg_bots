# ---- Helpers -----------------------------------------------------------------
.PHONY: help-i18n
help-i18n:
	@echo "Targets:"
	@echo "  compile-locales - compile i18n files for all available bots"
	@echo "  compile-locale  - compile i18n files for a specific bot: BOT=echo_bot"

# ---- I18N --------------------------------------------------------------------
.PHONY: compile-locales
compile-locales:
	$(PYTHON) scripts/compile_locales.py --all

.PHONY: compile-locale
compile-locale:
	$(PYTHON) scripts/compile_locales.py --bot $(BOT)
