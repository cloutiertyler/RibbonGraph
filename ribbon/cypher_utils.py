def constraints_expression_from_constraints(constraints, node_identifier="n"):
    neo4j_operator_mapping = {'!=': '<>', '=': '=', '<': '<', '>': '>', '>=': '>=', '<=': '<=', 'matches': '=~', }
    expression = ""
    for i, or_constraint in enumerate(constraints):
        for j, and_constraint in enumerate(or_constraint):
            attribute_name, operator, value = and_constraint
            node_attribute_string = "{}.{}".format(node_identifier, attribute_name)
            try:
                value = int(value)
                value = str(value)
            except ValueError:
                # Value is a string. Quote it.
                value = ''.join(["'", value, "'"])

            expression += ' '.join([node_attribute_string, neo4j_operator_mapping[operator], value])
            if j < len(or_constraint) - 1:
                expression += " AND "
        if i < len(constraints) - 1:
            expression += " OR "
    return expression
