from exceptions import (
    NodeNotFoundError, NodeTypeNotFoundError, GraphAPIError, MissingNodeTypeError, InvalidPropertyError,
    MalformedUpdateDictionaryError, )
import py2neo
import cypher_utils
from py2neo_additions import CypherTransactionManager
from node_model import Attribute, Relationship, NodeModel
from datetime import datetime
import logging
import inspect


DEFAULT_LIMIT = 100
DEFAULT_SKIP = 0
DEFAULT_CONSTRAINTS = None


class GraphAPI(object):
    def __init__(self, database_url=None, models=[]):
        """
        Initializes the graph with the models that make up the schema graph and
        an identifier for a url to a neo4j database.
        """
        self.neograph = py2neo.Graph() if not database_url else py2neo.Graph(database_url)
        self.models_dict = {}
        for model in models:
            self.models_dict[model.__name__] = model

    def setup_constraints(self):
        """
        Creates constraints for the graph based on the models in the schema
        graph.
        """
        for node_type in self.models_dict.values():
            if hasattr(node_type, "add_constraints_to_graph"):
                node_type.add_constraints_to_graph(self.neograph)

    def remove_constraints(self):
        """
        Removes all of the constraints set by the models in the schema graph.
        """
        for node_type in self.models_dict.values():
            if hasattr(node_type, "remove_constraints_from_graph"):
                node_type.remove_constraints_from_graph(self.neograph)

    def query_for_subgraphs(self, actor_id, query_dict, node_type):
        """
        This is used for returning a tree formatted subgraph of API where the
        query dict specifies which nodes should match the query and which
        relationships should be included for each node matching the query.

        """
        skip = query_dict.get('skip', DEFAULT_SKIP)
        order_by = query_dict.get('order_by', None)
        limit = query_dict.get('limit', DEFAULT_LIMIT)
        constraints = query_dict.get('where', DEFAULT_CONSTRAINTS)
        include_dict = query_dict.get('include', None)
        nodes = self._get_nodes_with_constraints(node_type, constraints, limit, skip, order_by)
        results = []
        for node in nodes:
            results.append(self.request_subgraph_at_node(actor_id, include_dict, node['id'], node_type))
        return results

    def update_subgraphs(self, actor_id, update_list):
        """
        Updates/creates a forest of trees specified in the update list.
        """

    def request_subgraph_at_node(self, actor_id, include_dict, id, node_type=None, tx=None):
        """
        Returns a tree subgraph of the Graph API rooted at the specified node,
        which includes attributes as specified in the include_dict.
        """
        if tx:
            return self._request_subgraph_at_node(tx, actor_id, include_dict, id, node_type)

        with CypherTransactionManager(self.neograph.cypher) as tx:
            return self._request_subgraph_at_node(tx, actor_id, include_dict, id, node_type)

    def update_subgraph_at_node(self, actor_id, update_type, update_dict, id=None, node_type=None, tx=None):
        """
        Updates/creates a tree subgraph of the Graph API rooted at the
        specified node, by making the modifications specified in the
        update_dict. All modifications are atomic/transactional.
        """
        change_stack = []
        if tx:
            results = self._update_subgraph_at_node(tx, actor_id, update_type, update_dict, id, node_type, change_stack)

        with CypherTransactionManager(self.neograph.cypher) as tx:
            results = self._update_subgraph_at_node(tx, actor_id, update_type, update_dict, id, node_type, change_stack)
            self.assert_allows_updates(actor_id, change_stack, tx)

        # Execute listeners outside the transaction because these listeners
        # operate under the assumption that the update has been committed.
        for change in change_stack:
            if isinstance(change[0], Attribute):
                attribute = change[0]
                node_id = change[1]
                old_value = change[2]
                new_value = change[3]
                attribute.did_set(self, actor_id, node_id, old_value, new_value)

            if isinstance(change[0], Relationship):
                relationship = change[0]
                node_id = change[1]
                related_node_id = change[2]
                change_type = change[3]
                if change_type == 'remove':
                    relationship.did_remove_edge(self, actor_id, node_id, related_node_id)
                else:
                    relationship.did_add_edge(self, actor_id, node_id, related_node_id)

        return results

    def assert_allows_updates(self, actor_id, change_stack, tx):
        if actor_id == -1:
            return
        for change in change_stack:
            if inspect.isclass(change[0]) and issubclass(change[0], NodeModel):
                node_model = change[0]
                change_type = change[1]
                if change_type == 'delete':
                    node_id = change[2]
                    node_model.assert_allows_delete(actor_id, self, node_id, tx=tx)
                else:
                    node_model.assert_allows_create(actor_id, self, tx=tx)

            if isinstance(change[0], Attribute):
                attribute = change[0]
                node_id = change[1]
                old_value = change[2]
                new_value = change[3]
                attribute.validate_value(self, actor_id, node_id, new_value, tx=tx)
                attribute.assert_allows_write(self, actor_id, node_id, new_value, tx=tx)

            if isinstance(change[0], Relationship):
                relationship = change[0]
                node_id = change[1]
                related_node_id = change[2]
                change_type = change[3]
                if change_type == 'remove':
                    relationship.assert_allows_remove_edge(
                        self,
                        actor_id,
                        node_id,
                        related_node_id,
                        tx=tx
                    )
                else:
                    relationship.assert_allows_add_edge(
                        self,
                        actor_id,
                        node_id,
                        related_node_id,
                        tx=tx
                    )


    def delete_nodes(self, actor_id, ids):
        """
        Deletes the set of nodes which corresponds to the ids provided.
        """

    ######### Internal methods #########
    def _get_node_type_of_node_with_id(self, tx, id):
        tx.append('MATCH (n) WHERE n.id = {id} RETURN labels(n)', {'id': id})
        node = tx.process()[-1].one
        if not node:
            raise NodeNotFoundError(id)
        return node[0]

    def _nodes_are_related_by(self, tx, a_id, b_id, rel_type):
        tx.append(
            'MATCH (a {{ id:{aid} }})-[r:{rel_type}]-(b {{ id:{bid} }}) '
            'RETURN r'.format(
                aid=a_id,
                rel_type=rel_type,
                bid=b_id))
        results = tx.process()[-1].one
        return results != None

    def _nodes_are_related_from_a_to_b_by(self, tx, a_id, b_id, rel_type):
        tx.append(
            'MATCH (a {{ id:{aid} }})-[r:{rel_type}]->(b {{ id:{bid} }}) '
            'RETURN r'.format(
                aid=a_id,
                rel_type=rel_type,
                bid=b_id))
        results = tx.process()[-1].one
        return results != None

    def _get_node_with_id(self, tx, id, node_type=None):
        node = None
        if node_type:
            node_model = self.models_dict.get(node_type, None)
            if not node_model:
                # No query injections please.
                raise NodeTypeNotFoundError(node_type)
            tx.append('MATCH (n:{node_type}) '
                      'WHERE n.id = {{id}} '
                      'RETURN n'.format(node_type=node_type),
                      {'id': id})
        else:
            tx.append('MATCH (n) WHERE n.id = {id} RETURN n', {'id': id})
        node = tx.process()[-1].one
        if not node:
            raise NodeNotFoundError(id)
        return node

    def _get_nodes_with_constraints(self, node_type, constraints, limit, skip, order_by):
        # TODO: AAAAAHHHH
        # CYPHER INJECTION POTENTIAL! WATCHOUT!
        constraint_query = ''
        # Node type required otherwise you pick up internal type nodes as well.
        constraint_query += 'MATCH (n:{})'.format(node_type)
        if constraints:
            constraint_query += ' WHERE '
            constraint_query += cypher_utils.constraints_expression_from_constraints(constraints)
        constraint_query += ' RETURN n'
        if order_by:
            constraint_query += ' ORDER BY "{}"'.format(order_by[0])
            constraint_query += ' {}'.format(order_by[1].upper())
        constraint_query += ' SKIP {}'.format(skip)
        constraint_query += ' LIMIT {}'.format(limit)
        return map(lambda r: r[0], self.neograph.cypher.execute(constraint_query))

    def _get_new_global_unique_id(self, tx):
        # Create the global unique id node if necessary
        tx.append(
            'MERGE (id:_GlobalUniqueId) '
            'ON CREATE SET id.count = 1 '
            'ON MATCH SET id.count = id.count + 1 '
            'RETURN id.count AS generated_id')
        # Return the id of first result of the last transaction
        return tx.process()[-1].one

    def _create_node_of_type(self, tx, creator_id, node_type):
        new_id = self._get_new_global_unique_id(tx)
        created_at = datetime.now()
        updated_at = created_at
        tx.append(
            py2neo.cypher.CreateNode(
                node_type,
                id=new_id,
                created_at=created_at.isoformat(),
                updated_at=updated_at.isoformat(),
                created_by=creator_id
            )
        )
        return new_id

    def _create_node_of_relationship_type(self, tx, actor_id, relationship):
        # If there was no node id we must create it.
        return self._create_node_of_type(tx, actor_id, relationship.target_model_name)

    def _delete_node(self, tx, id):
        tx.append('MATCH (n) WHERE n.id = {id} DETACH DELETE n', {'id': id})

    def _request_subgraph_at_node(self, tx, actor_id, include_dict, id, node_type=None):
        """
        Internal method

        This method recursively requests the tree of nodes specified in the
        include dict, if permission is granted for the operation.
        """
        if not node_type:
            node_type = self._get_node_type_of_node_with_id(tx, id)

        node_model = self.models_dict.get(node_type, None)
        if not node_model:
            raise NodeTypeNotFoundError(node_type)  # No query injections please.
        node = self._get_node_with_id(tx, id, node_type)

        results = {}
        # Always include the id of the current node.
        results['id'] = node['id']
        if not include_dict:
            return results

        for include_key in include_dict:
            if include_key in node_model.attributes():
                attribute = node_model.attributes()[include_key]

                if actor_id != -1:
                    attribute.assert_allows_read(self, actor_id, node['id'], tx=tx)

                results[include_key] = node[include_key]

            elif include_key in node_model.relationships():
                relationship = node_model.relationships()[include_key]

                nested_query_dict = include_dict[relationship.name]
                skip = nested_query_dict.get('skip', DEFAULT_SKIP) if nested_query_dict else DEFAULT_SKIP
                limit = nested_query_dict.get('limit', DEFAULT_LIMIT) if nested_query_dict else DEFAULT_LIMIT
                order_by = nested_query_dict.get('order_by', None) if nested_query_dict else None
                constraints = nested_query_dict.get(
                    'where', DEFAULT_CONSTRAINTS) if nested_query_dict else DEFAULT_CONSTRAINTS
                nested_include_dict = nested_query_dict.get('include', None) if nested_query_dict else None

                if actor_id != -1:
                    relationship.assert_allows_read(self, actor_id, node['id'], tx=tx)

                related_nodes = relationship.get_related_nodes_with_constraints(
                    tx, node['id'], constraints, limit, skip, order_by)
                if relationship.max_edges == 1:
                    results[relationship.name] = None
                    if related_nodes:
                        related_node = related_nodes[0]
                        results[relationship.name] = self._request_subgraph_at_node(
                            tx, actor_id, nested_include_dict, related_node['id'])
                else:
                    results[relationship.name] = []
                    for related_node in related_nodes:
                        results[relationship.name].append(self._request_subgraph_at_node(
                            tx, actor_id, nested_include_dict, related_node['id']))
            else:
                raise InvalidPropertyError("There is no '{}' property.".format(include_key))
        return results

    def _update_subgraph_at_node(self, tx, actor_id, update_type, update_dict, id=None, node_type=None, change_stack=None):
        """
        Internal method

        Recursively updates the tree of nodes specified in the update_dict if
        permission is granted for the operation.
        """
        return_dict = {}
        if update_type == 'create':
            if not node_type:
                raise MissingNodeTypeError('No node type specified for new node.')
            if id != None:
                raise APIException('id should not be provided for a new node.')

        elif update_type == 'update':
            if id == None:
                raise APIException('id must be specified to update a node.')

        elif update_type == 'delete':
            if id == None:
                raise APIException('id must be specified to delete a node.')

        else:
            raise APIException('invalid update')

        if update_type != 'create':
            node_type = self._get_node_type_of_node_with_id(tx, id)

        node_model = self.models_dict.get(node_type, None)
        if not node_model:
            raise NodeTypeNotFoundError(node_type)  # No query injections please.

        if update_type == 'create':
            id = self._create_node_of_type(tx, actor_id, node_type)
            if change_stack != None:
                change_stack.append((node_model, 'create'))

        node = self._get_node_with_id(tx, id, node_type)
        for update_key in update_dict:
            if update_key == 'id':
                continue

            elif update_key in node_model.attributes():
                attribute = node_model.attributes()[update_key]
                new_value = update_dict[update_key]
                return_dict[update_key] = self._update_attribute(tx, actor_id, node, attribute, new_value, change_stack)

            elif update_key in node_model.relationships():
                relationship = node_model.relationships()[update_key]
                relationship_update_dict = update_dict[update_key]
                if not isinstance(relationship_update_dict, dict):
                    raise MalformedUpdateDictionaryError('Malformed update dictionary.')
                relationship_update_types = set(['attach', 'detach', 'delete'])

                if relationship.max_edges == 1 and all(map(lambda value: isinstance(value, dict), relationship_update_dict.values())):
                    if len(relationship_update_dict) != 1:
                        raise MalformedUpdateDictionaryError('To one relationships must specify only one of attach update or delete.')
                    update_type = relationship_update_dict.keys()[0]
                    if update_type not in relationship_update_types:
                        raise MalformedUpdateDictionaryError('Relationships must specify only attach update or delete.')
                    return_dict[update_key] = self._update_to_one_relationship(tx, actor_id, node, relationship, relationship_update_dict, change_stack)

                elif ((not relationship.max_edges or relationship.max_edges > 1)
                        and all(map(lambda value: isinstance(value, list), relationship_update_dict.values()))):

                    if any(map(lambda key: key not in relationship_update_types, relationship_update_dict)):
                        raise MalformedUpdateDictionaryError('Relationships must specify only attach update or delete.')
                    return_dict[update_key] = self._update_to_many_relationship(tx, actor_id, node, relationship, relationship_update_dict, change_stack)

                else:
                    # Trying to pass an array for a to one relationship.
                    raise MalformedUpdateDictionaryError('Malformed update dictionary.')
            else:
                raise InvalidPropertyError("There is no '{}' property.".format(update_key))

        if update_type == 'delete':
            self._delete_node(tx, id)
            if change_stack != None:
                change_stack.append((node_model, 'delete', id))
        else:
            return_dict['id'] = id

        return return_dict

    def _update_attribute(self, tx, actor_id, node, attribute, new_value, change_stack=None):
        """
        Updates the attribute on the provided node with the new value.
        """
        if change_stack != None:
            old_value = attribute.get_value(tx, node['id'])
            change_stack.append((attribute, node['id'], old_value, new_value))
        attribute.set_value(tx, node['id'], new_value)
        return new_value

    def _update_to_one_relationship(self, tx, actor_id, node, relationship, update_dict, change_stack=None):
        """
        Updates the to one relationship in accordance with the provided update
        dict if permitted and then recursively calls update on the nested node.
        """
        relationship_update_type = update_dict.keys()[0]
        update_value = update_dict[relationship_update_type]
        rev_relationship = relationship.get_reverse_relationship(self.models_dict)

        # If there is a currently related node, remove it.
        current_related_nodes = relationship.get_related_nodes_with_constraints(tx, node['id'])
        current_related_node = current_related_nodes[0] if current_related_nodes else None

        if relationship_update_type == 'delete':
            if not current_related_node or current_related_node['id'] != update_value['id']:
                raise APIException('Cannot delele node {} which is not related.'.format(update_value['id']))
            return self._update_subgraph_at_node(tx, actor_id, 'delete', update_value, update_value['id'], change_stack=change_stack)

        elif relationship_update_type == 'detach':
            if not current_related_node or current_related_node['id'] != update_value['id']:
                raise APIException('Cannot detach node {} which is not related.'.format(update_value['id']))

            relationship.remove(tx, node['id'], current_related_node['id'])
            if change_stack != None:
                change_stack.append((relationship, node['id'], current_related_node['id'], 'detach'))
                if rev_relationship:
                    change_stack.append((rev_relationship, current_related_node['id'], node['id'], 'detach'))

            return self._update_subgraph_at_node(tx, actor_id, 'update', update_value, update_value['id'], change_stack=change_stack)

        elif relationship_update_type == 'attach':
            if current_related_node:
                if 'id' not in update_value or current_related_node['id'] != update_value['id']:
                    relationship.remove(tx, node['id'], current_related_node['id'])

                    if change_stack != None:
                        change_stack.append((relationship, node['id'], current_related_node['id'], 'detach'))
                        if rev_relationship:
                            change_stack.append((rev_relationship, current_related_node['id'], node['id'], 'detach'))

            if 'id' not in update_value:
                update_value['id'] = self._create_node_of_relationship_type(tx, actor_id, relationship)
                if change_stack != None:
                    node_model = self.models_dict[relationship.target_model_name]
                    change_stack.append((node_model, 'create'))

            related_node = self._get_node_with_id(tx, update_value['id'])

            relationship.add(tx, node['id'], update_value['id'])

            if change_stack != None:
                change_stack.append((relationship, node['id'], related_node['id'], 'add'))
                if rev_relationship:
                    change_stack.append((rev_relationship, related_node['id'], node['id'], 'add'))

            return self._update_subgraph_at_node(tx, actor_id, 'update', update_value, update_value['id'], change_stack=change_stack)

    def _update_to_many_relationship(self, tx, actor_id, node, relationship, update_dict, change_stack=None):
        """
        Updates the to many relationship in accordance with the provided update
        list if permitted and then recursively calls update on each of the
        nested nodes.
        """
        return_list = []
        for relationship_update_type, update_list in update_dict.iteritems():
            rev_relationship = relationship.get_reverse_relationship(self.models_dict)

            if relationship_update_type == 'delete':
                for update_value in update_list:
                    related_node = self._get_node_with_id(tx, update_value['id'])
                    return_list.append(self._update_subgraph_at_node(tx, actor_id, 'delete', update_value, update_value['id'], change_stack=change_stack))

            elif relationship_update_type == 'detach':
                edges_to_detach = update_list
                for update_value in edges_to_detach:
                    related_node = self._get_node_with_id(tx, update_value['id'])

                    relationship.remove(tx, node['id'], update_value['id'])

                    if change_stack != None:
                        change_stack.append((relationship, node['id'], related_node['id'], 'remove'))
                        if rev_relationship:
                            change_stack.append((rev_relationship, related_node['id'], node['id'], 'remove'))

                    return_list.append(self._update_subgraph_at_node(tx, actor_id, 'update', update_value, update_value['id'], change_stack=change_stack))

            elif relationship_update_type == 'attach':
                # All the dictionaries without ids.
                nodes_to_create = filter(lambda e: 'id' not in e, update_list)
                for new_node_dict in nodes_to_create:
                    new_node_dict['id'] = self._create_node_of_relationship_type(tx, actor_id, relationship)
                    if change_stack != None:
                        node_model = self.models_dict[relationship.target_model_name]
                        change_stack.append((node_model, 'create'))

                # We have already added the id's into the objects that
                # were missing them so they will be in edges to add.
                edges_to_attach = update_list
                current_related_node_id_set = map(lambda crn: crn['id'], relationship.get_related_nodes_with_constraints(tx, node['id']))
                for update_value in filter(lambda update_value: update_value['id'] not in current_related_node_id_set, edges_to_attach):
                    related_node = self._get_node_with_id(tx, update_value['id'])

                    relationship.add(tx, node['id'], update_value['id'])

                    if change_stack != None:
                        change_stack.append((relationship, node['id'], related_node['id'], 'add'))
                        if rev_relationship:
                            change_stack.append((rev_relationship, related_node['id'], node['id'], 'add'))

                    return_list.append(self._update_subgraph_at_node(tx, actor_id, 'update', update_value, update_value['id'], change_stack=change_stack))

