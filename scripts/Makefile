ROOT := $(realpath $(dir $(lastword $(MAKEFILE_LIST)))/..)
TS := $(shell date +%Y%m%d-%H%M%S)

.PHONY: clean package

clean:
	git -C $(ROOT) clean -Xfd

package:
	cd $(ROOT) && mkdir -p dist && git archive --format=tar.gz --output=dist/dedoopsie-$(TS).tgz HEAD

