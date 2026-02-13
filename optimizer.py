from ortools.constraint_solver import pywrapcp, routing_enums_pb2


def optimize_routes(
    time_matrix,
    time_windows,
    service_times,
    num_vehicles,
    start_time,
    buffer_realista
):

    num_locations = len(time_matrix)

    manager = pywrapcp.RoutingIndexManager(
        num_locations,
        num_vehicles,
        [0] * num_vehicles,
        [0] * num_vehicles
    )

    routing = pywrapcp.RoutingModel(manager)

    # 🔥 TIEMPO CON BUFFER
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)

        travel_time = int(time_matrix[from_node][to_node] * buffer_realista)
        service_time = service_times[from_node]

        return travel_time + service_time

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    routing.AddDimension(
        transit_callback_index,
        12 * 60 * 60,
        24 * 60 * 60,
        False,
        "Time"
    )

    time_dimension = routing.GetDimensionOrDie("Time")

    PENALTY = 10_000_000

    for node in range(1, num_locations):
        routing.AddDisjunction(
            [manager.NodeToIndex(node)],
            PENALTY
        )

    # Ventanas
    for node, window in enumerate(time_windows):
        index = manager.NodeToIndex(node)
        time_dimension.CumulVar(index).SetRange(window[0], window[1])

    # Hora exacta salida
    for vehicle_id in range(num_vehicles):
        start_index = routing.Start(vehicle_id)
        time_dimension.CumulVar(start_index).SetRange(start_time, start_time)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 10

    solution = routing.SolveWithParameters(search_parameters)

    if solution is None:
        return None

    routes = [[] for _ in range(num_vehicles)]
    visited_nodes = set()

    for vehicle_id in range(num_vehicles):
        index = routing.Start(vehicle_id)

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)

            routes[vehicle_id].append({
                "node": node,
                "arrival": solution.Value(time_dimension.CumulVar(index)),
                "service": service_times[node]
            })

            visited_nodes.add(node)
            index = solution.Value(routing.NextVar(index))

        node = manager.IndexToNode(index)

        routes[vehicle_id].append({
            "node": node,
            "arrival": solution.Value(time_dimension.CumulVar(index)),
            "service": 0
        })

        visited_nodes.add(node)

    unserved = [
        node for node in range(1, num_locations)
        if node not in visited_nodes
    ]

    return {
        "routes": routes,
        "unserved": unserved
    }
