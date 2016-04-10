class CypherTransactionManager(object):
    def __init__(self, cypher):
        self.cypher = cypher
        self.tx = None

    def __enter__(self):
        self.tx = self.cypher.begin()
        return self.tx

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            self.tx.rollback()
        else:
            self.tx.commit()
