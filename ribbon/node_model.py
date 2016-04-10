import types
import inspect
import cypher_utils
from exceptions import PermissionDenied, InvalidValueError, NodeTypeNotFoundError


class Allows(object):
    """
    Default permissions definitions
    """

    @staticmethod
    def creator(self, graph, actor_id, node_id, tx):
        creator_id = graph.request_subgraph_at_node(-1, {'created_by': None}, node_id, tx=tx)['created_by']
        if not actor_id == creator_id:
            raise PermissionDenied("{}: User {} is not the creator.".format(self.name, actor_id))

    @staticmethod
    def public(self, graph, actor_id, node_id, tx):
        pass

    @staticmethod
    def internal(self, graph, actor_id, node_id, tx):
        raise PermissionDenied()


class Attribute(object):
    def __init__(self, read=Allows.creator, write=Allows.creator, name=None):
        self.read = types.MethodType(read, self)
        self.write = types.MethodType(write, self)

        self.name = name

    def set_value(self, tx, id, value):
        """
        WARNING! Unsafe to pass unvalidated attributes to this function!
        """
        tx.append("MATCH (n) WHERE n.id = {{id}} SET n.{attribute_name} = {{value}}".format(attribute_name=self.name),
                  {"id": id,
                   "value": value})

    def get_value(self, tx, id):
        """
        WARNING! Unsafe to pass unvalidated attributes to this function!
        """
        tx.append("MATCH (n) WHERE n.id = {id} RETURN n", {"id": id})
        n = tx.process()[-1].one
        return n[self.name]

    # Property observers
    def did_set(self, graph, actor_id, node_id, old_value, value):
        pass

    def validate_value(self, graph, actor_id, node_id, new_value, tx=None):
        pass

    def assert_allows_read(self, graph, actor_id, node_id, tx=None):
        self.read(graph, actor_id, node_id, tx)

    def assert_allows_write(self, graph, actor_id, node_id, new_value, tx=None):
        self.write(graph, actor_id, node_id, tx)

class FileAttribute(Attribute):
    pass


class Relationship(object):
    def __init__(self,
                 target_model_name,
                 rel_type=None,
                 direction=None,
                 max_edges=None,
                 read=Allows.creator,
                 add_edge=Allows.creator,
                 remove_edge=Allows.creator,
                 name=None):
        self.target_model_name = target_model_name
        self.rel_type = rel_type
        self.max_edges = max_edges
        self.read = types.MethodType(read, self)
        self.add_edge = types.MethodType(add_edge, self)
        self.remove_edge = types.MethodType(remove_edge, self)
        self.direction = direction

        self.name = name

    @property
    def rel_type(self):
        return self._rel_type if self._rel_type else self.name

    @rel_type.setter
    def rel_type(self, value):
        self._rel_type = value

    def did_remove_edge(self, graph, actor_id, node_id, id_removed):
        pass

    def did_add_edge(self, graph, actor_id, node_id, id_added):
        pass

    def assert_allows_read(self, graph, actor_id, node_id, tx=None):
        self.read(graph, actor_id, node_id, tx)

    def assert_allows_add_edge(self, graph, actor_id, node_id, id_to_add, tx=None):
        self.add_edge(graph, actor_id, node_id, tx)

    def assert_allows_remove_edge(self, graph, actor_id, node_id, id_to_add, tx=None):
        self.remove_edge(graph, actor_id, node_id, tx)

    def get_reverse_relationship(self, models_dict):
        node_model = models_dict.get(self.target_model_name, None)
        if not node_model:
            raise NodeTypeNotFoundError(self.target_model_name)  # No query injections please.
        for rev_relationship in node_model.relationships().values():
            if rev_relationship.rel_type == self.rel_type:
                if not self.direction:
                    return rev_relationship
                if rev_relationship.direction != self.direction:
                    return rev_relationship
        return None

    def get_related_nodes_with_constraints(self, tx, from_node_id, constraints=None, limit=100, skip=0, order_by=None):
        constraint_query = ""
        if self.direction:
            if self.direction == "incoming":
                constraint_query += "MATCH (u {{ id:{} }})<-[:{}]-(v)".format(from_node_id, self.rel_type)
            else:
                constraint_query += "MATCH (u {{ id:{} }})-[:{}]->(v)".format(from_node_id, self.rel_type)
        else:
            constraint_query += "MATCH (u {{ id:{} }})-[:{}]-(v)".format(from_node_id, self.rel_type)
        if constraints:
            constraint_query += " WHERE "
            constraint_query += cypher_utils.constraints_expression_from_constraints(constraints, node_identifier='v')
        constraint_query += " RETURN v"
        if order_by:
            # TODO: I'm thinking this might be a security hole in that it
            # allows you to order by fields that you don't have permission to
            # view. Should fix this eventually.
            constraint_query += ' ORDER BY v.{}'.format(order_by[0])
            constraint_query += ' {}'.format(order_by[1].upper())
        constraint_query += " SKIP {}".format(skip)
        constraint_query += " LIMIT {}".format(limit)
        tx.append(constraint_query)
        return map(lambda r: r[0], tx.process()[-1])

    def remove(self, tx, from_node_id, to_node_id):
        if self.direction == 'incoming':
            remove_query = "MATCH (a)<-[r:{rel_type}]-(b) WHERE a.id = {{aid}} AND b.id = {{bid}} DELETE r"
        elif self.direction == 'outgoing':
            remove_query = "MATCH (a)-[r:{rel_type}]->(b) WHERE a.id = {{aid}} AND b.id = {{bid}} DELETE r"
        else:
            remove_query = "MATCH (a)-[r:{rel_type}]-(b) WHERE a.id = {{aid}} AND b.id = {{bid}} DELETE r"
        tx.append(remove_query.format(rel_type=self.rel_type), {'aid': from_node_id, 'bid': to_node_id})

    def add(self, tx, from_node_id, to_node_id):
        # Create the relationship
        if self.direction == 'incoming':
            create_query = "MATCH (a),(b) WHERE a.id = {{aid}} AND b.id = {{bid}} MERGE (a)<-[r:{rel_type}]-(b) RETURN r"
        else:
            # Either outgoing or unspecified.
            create_query = "MATCH (a),(b) WHERE a.id = {{aid}} AND b.id = {{bid}} MERGE (a)-[r:{rel_type}]->(b) RETURN r"
        tx.append(create_query.format(rel_type=self.rel_type), {'aid': from_node_id, 'bid': to_node_id})


class NodeModel(object):
    """
    Permission types can be, 'owner', 'internal', 'public', or a function that returns a
    boolean indicating whether the operation is allowed.
    """

    # Names must be specified for these attributes because they may be accessed
    # directly instead of going through the class properties.
    created_by = Attribute(read=Allows.internal, write=Allows.internal, name='created_by')
    updated_at = Attribute(write=Allows.internal, name='updated_at')
    created_at = Attribute(write=Allows.internal, name='created_at')

    @classmethod
    def assert_allows_create(self, actor_id, graph, tx=None):
        pass

    @classmethod
    def assert_allows_delete(self, actor_id, graph, node_id, tx=None):
        pass

    @classmethod
    def attributes(self):
        attr = dict(inspect.getmembers(self, lambda v: isinstance(v, Attribute)))
        for k, v in attr.iteritems():
            v.name = k
        return attr

    @classmethod
    def relationships(self):
        rels = dict(inspect.getmembers(self, lambda v: isinstance(v, Relationship)))
        for k, v in rels.iteritems():
            v.name = k
        return rels
