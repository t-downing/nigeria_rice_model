from BPTK_Py import Model
from BPTK_Py import sd_functions as sd
from import_data import *
from general_functions import *


class ModelActor:
    def __init__(self, model: Model, name: str):
        self.model = model
        self.name = name

        # list all possible actor variables
        self.stock = None
        self.leadtime = None
        self.supply = None
        self.cash = None
        self.revenue = None
        self.revenue_fcast = None
        self.production = None
        self.demand = None
        self.total_demand_on_actor = None
        self.d2s_ratio = None
        self.price = None
        
        self.income = None
        self.pc_demand = None
        self.comm_needs = None
        self.max_fraction_of_income = None
        self.population = None
        self.received_volume = None


class Consumer(ModelActor):
    def __init__(
            self,
            model: Model,
            name: str,
            max_fraction_of_income: float = 1.0, 
            comm_needs: float = 1.0,
            income_baseline: float = 1.0,
            population: float = 1.0
            
    ):
        super().__init__(model, name)
        self.income = self.model.converter(f"{name} Income")
        self.income.equation = income_baseline
        self.max_fraction_of_income = self.model.constant(
            f"{name} Max Fraction of Income Spent on Commodity"
        )
        self.max_fraction_of_income.equation = max_fraction_of_income
        self.comm_needs = self.model.constant(f"{name} Commodity Needs")
        self.comm_needs.equation = comm_needs
        self.population = self.model.converter(f"{name} Population")
        self.population.equation = population

        self.pc_demand = self.model.converter(f"{name} Per Capita Demand")
        self.demand = self.model.converter(f"{name} Total Demand")
        self.demand.equation = self.pc_demand * self.population

        self.initial_total_needs = self.model.constant(f"{name} Initial Total Needs")
        self.initial_total_needs.equation = comm_needs * population


class SupplyChainActor(ModelActor):
    def __init__(
            self,
            model: Model,
            name: str,
            leadtime: float = 7.0
    ):
        super().__init__(model, name)

        zero_flow = model.flow("Zero Flow")
        zero_flow.equation = 0.0

        # physical stock
        self.stock = model.stock(f"{name} Stock")
        self.stock.equation = zero_flow
        self.leadtime = model.converter(f"{name} Leadtime")
        self.leadtime.equation = leadtime
        self.supply = model.converter(f"{name} Supply")
        self.supply.equation = self.stock / self.leadtime

        # cash
        self.cash = model.stock(f"{name} Cash")
        self.cash.equation = zero_flow

        # business model
        self.revenue = model.converter(f"{name} Revenue")
        self.revenue.equation = 0.0
        self.revenue_fcast = model.converter(f"{name} Revenue Forecast")
        self.revenue_fcast.equation = self.revenue
        self.demand = model.converter(f"{name} Demand")

        # price
        self.d2s_ratio = model.converter(f"{name} Demand-to-Supply Ratio")
        self.total_demand_on_actor = model.converter(f"Total Demand on {name}")
        self.total_demand_on_actor.equation = 0.0
        self.d2s_ratio.equation = self.total_demand_on_actor / self.supply
        self.price = model.converter(f"{name} Price")
        self.price.equation = (
            smooth_model_variable(
                model,
                self.d2s_ratio,
                7.0,
                1.0
            )
        )

    def connect_to_downstream_sca(self, downstream_actor: ModelActor):
        # demand
        downstream_actor.demand.equation = downstream_actor.revenue_fcast / self.price
        self.total_demand_on_actor.equation += downstream_actor.demand
        
        # volume
        volume = self.model.flow(f"{self.name} to {downstream_actor.name} Volume")
        volume.equation = sd.min(downstream_actor.demand, self.supply)
        self.stock.equation -= volume
        downstream_actor.stock.equation += volume     

        # downstream price
        downstream_actor.price.equation *= smooth_model_variable(
            self.model,
            self.price,
            7.0,
            self.price
        )

        # cashflow
        cashflow = self.model.flow(f"{downstream_actor.name} to {self.name} Cashflow")
        cashflow.equation = self.price * volume
        self.cash.equation += cashflow
        downstream_actor.cash.equation -= cashflow
        self.revenue.equation += cashflow

    def connect_to_consumers(self, consumers: list[ModelActor]):
        # demand
        for consumer in consumers:
            # per capita consumer demand
            consumer.pc_demand.equation = sd.min(
                consumer.comm_needs,
                consumer.income * consumer.max_fraction_of_income / self.price
            )
            # total consumer demand
            self.total_demand_on_actor.equation += consumer.demand

        # fill rate
        total_volume = self.model.flow(f"Total {self.name} to Consumer Volume")
        total_volume.equation = sd.min(
            self.total_demand_on_actor,
            self.supply
        )
        fill_rate = self.model.flow(f"{self.name} to Consumer Fill Rate")
        fill_rate.equation = total_volume / self.total_demand_on_actor

        # volumes and cashflows
        for consumer in consumers:
            consumer.received_volume = self.model.flow(f"{self.name} to {consumer.name} Volume")
            consumer.received_volume.equation = fill_rate * consumer.demand
            self.stock.equation -= consumer.received_volume

            cashflow = self.model.flow(f"{consumer.name} to {self.name} Cashflow")
            cashflow.equation = self.price * consumer.received_volume
            self.cash.equation += cashflow
            self.revenue.equation += cashflow


def set_model_logic(start_serial, stop_serial, df):
    """ Setup model based on start date, end date, and df containing input data """

    time_step_in_days = 1.0

    model = Model(
        starttime=start_serial,
        stoptime=stop_serial,
        dt=1.0 * time_step_in_days,
    )

    # set parameters
    population = 5000000
    comm_needs = 1.0
    leadtime = 7.0

    # create actors
    trader = SupplyChainActor(model, "Trader", leadtime=leadtime)
    wholesaler = SupplyChainActor(model, "Wholesaler", leadtime=leadtime)
    retailer = SupplyChainActor(model, "Retailer", leadtime=leadtime)
    host_population = Consumer(
        model,
        "Host Population",
        population=population,
        comm_needs=comm_needs
    )
    consumers = [
        host_population
    ]

    # connect to data
    data_prod_usda = create_model_data_variable(model, df, "Production (USDA)")
    production = model.flow("Production")
    production.equation = data_prod_usda
    trader.stock.equation += production

    # connect actors
    trader.connect_to_downstream_sca(wholesaler)
    wholesaler.connect_to_downstream_sca(retailer)
    retailer.connect_to_consumers(consumers)

    # set parameters
    trader.stock.initial_value = leadtime * comm_needs * population
    wholesaler.stock.initial_value = leadtime * comm_needs * population
    retailer.stock.initial_value = leadtime * comm_needs * population

    return model

