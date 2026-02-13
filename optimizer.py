from ortools.constraint_solver import pywrapcp, routing_enums_pb2


def optimize_routes(time_matrix, time_windows, service_times, num_vehicles, start_time):
    """
    Optimiza rutas considerando:
    - Acopio como inicio y fin (nodo 0)
    - Uno o varios vehículos
    - Tiempo de viaje + tiempo de espera por parada
    - Ventanas horarias por nodo
    - Jornada máxima del vehículo
    - Posibilidad de omitir paradas (con penalización)

    Retorna:
    {
        "routes": [
            [
                {"node": int, "arrival": int, "service": int},
                ...
            ],
            ...
        ],
        "unserved": [int, int, ...]
    }
    """

    num_locations = len(time_matrix)

    # =========================
    # 🚚 INICIO / FIN
    # =========================
    starts = [0] * num_vehicles
    ends = [0] * num_vehicles

    manager = pywrapcp.RoutingIndexManager(
        num_locations,
        num_vehicles,
        starts,
        ends
    )

    routing = pywrapcp.RoutingModel(manager)

    # =========================
    # ⏱️ CALLBACK DE TIEMPO
    # =========================
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)

        travel_time = time_matrix[from_node][to_node]
        service_time = service_times[from_node]

        return travel_time + service_time

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # =========================
    # ⏱️ DIMENSIÓN DE TIEMPO
    # =========================
    routing.AddDimension(
        transit_callback_index,
        12 * 60 * 60,      # slack permitido
        24 * 60 * 60,      # horizonte máximo 24h
        False,
        "Time"
    )

    time_dimension = routing.GetDimensionOrDie("Time")

    # =========================
    # 🚫 PERMITIR OMITIR CLIENTES
    # =========================
    PENALTY = 10_000_000  # penalización alta

    for node in range(1, num_locations):
        routing.AddDisjunction(
            [manager.NodeToIndex(node)],
            PENALTY
        )

    # =========================
    # 🕒 VENTANAS HORARIAS
    # =========================
    for node, window in enumerate(time_windows):
        index = manager.NodeToIndex(node)
        time_dimension.CumulVar(index).SetRange(
            window[0],
            window[1]
        )

    # Aplicar también al inicio de cada vehículo (acopio)
    for vehicle_id in range(num_vehicles):
        start_index = routing.Start(vehicle_id)

        # 🔥 FORZAR hora de salida real
        time_dimension.CumulVar(start_index).SetRange(
            start_time,
            start_time
        )

    # =========================
    # 🔍 PARÁMETROS DE BÚSQUEDA
    # =========================
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

    # =========================
    # 📍 EXTRAER RUTAS
    # =========================
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

        # Nodo final (acopio de regreso)
        node = manager.IndexToNode(index)
        routes[vehicle_id].append({
            "node": node,
            "arrival": solution.Value(time_dimension.CumulVar(index)),
            "service": 0
        })

        visited_nodes.add(node)

    # =========================
    # 🔴 PARADAS NO ATENDIDAS
    # =========================
    unserved = []

    for node in range(1, num_locations):
        if node not in visited_nodes:
            unserved.append(node)

    return {
        "routes": routes,
        "unserved": unserved
    }
