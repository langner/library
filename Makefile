# I want to split the main library into subsets automatically,
#  but I assume we already have the splits, which makes it easier
#  to identify the targets.
SPLITS = $(shell ls [a-z]*/*.bib | sed 's/ /\\ /g')

.PHONY: default all
default: fix split small

.PHONY: fix
fix: library.log
library.log: library.bib library.py */*.pdf
	./library.py fix > library.log

.PHONY: split
split: $(SPLITS)
$(SPLITS): library.bib library.py
	./library.py split "$@" > /dev/null

.PHONY: small
small: library.small.bib
library.small.bib: library.bib
	cat library.bib | sed '/^\tabstract = .*/d' \
	                | sed '/^\tlocalfile = .*/d' > library.small.bib

.PHONY: clean
clean:
	rm -rvf library.small.bib
