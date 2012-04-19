
RIAKVERSION=riak-1.1.2

riak.download:
	if [ ! -d $(RIAKVERSION) ]; then \
		wget http://downloads.basho.com/riak/CURRENT/$(RIAKVERSION).tar.gz; \
		tar xzf $(RIAKVERSION).tar.gz; \
		rm $(RIAKVERSION).tar.gz; \
		cd $(RIAKVERSION); \
		make all; \
	fi

riak.devinstall: riak.download
	if [ ! -d $(RIAKVERSION)/dev ]; then \
		cd $(RIAKVERSION); \
		make devrel; \
	fi

riak.devstart: riak.devinstall
	./$(RIAKVERSION)/dev/dev1/bin/riak start
	@./$(RIAKVERSION)/dev/dev2/bin/riak start
	@./$(RIAKVERSION)/dev/dev3/bin/riak start
	@./$(RIAKVERSION)/dev/dev2/bin/riak-admin join dev1@127.0.0.1
	@./$(RIAKVERSION)/dev/dev3/bin/riak-admin join dev1@127.0.0.1

test:
	py.test .

