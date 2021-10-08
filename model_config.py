from BPTK_Py import Model
from BPTK_Py import sd_functions as sd
from import_data import *
from general_functions import *


class SupplyChainActor:
    def __init__(self, model: Model, name, upstream_actor=None, downstream_actor=None):
        self.model = model
        self.name = name
        self.upstream_actor = upstream_actor
        self.downstream_actor = downstream_actor

        zero_flow = model.flow("Zero Flow")
        zero_flow.equation = 0.0

        # physical
        self.stock = model.stock(f"{name} Stock")
        self.stock.equation = zero_flow
        self.leadtime = model.constant(f"{name} Leadtime")
        self.supply = model.converter(f"{name} Supply")
        self.supply.equation = self.stock / self.leadtime

        # cash
        self.cash = model.stock(f"{name} Cash")
        self.cash.equation = zero_flow
        # cash.equation = (
        #         self.cash_in()
        #         - self.model.flow(f"{name} to {upstream_actor} Cashflow")
        # )

        eggs = model.stock(f"{name} Eggs")
        eggs.initial_value = 100.0
        eggs.equation = zero_flow
        self.eggs = eggs

        egg_demand = model.converter(f"{name} Egg Demand")
        egg_demand.equation = 10.0
        self.egg_demand = egg_demand

    def __str__(self):
        return (
            f"{self.name} is a Supply Chain Actor. "
            f"The {self.upstream_actor} is upstream and the "
            f"{self.downstream_actor} is downstream."
        )

    def connect_to_upstream(self, upstream_actor):
        volume = self.model.flow(f"{upstream_actor.name} to {self.name} Volume")
        volume.equation = sd.min(self.demand(), upstream_actor.supply)
        self.stock.equation += volume
        upstream_actor.stock.equation -= volume
        cashflow = self.model.flow(f"{self.name} to {upstream_actor.name} Cashflow")
        cashflow.equation = volume * upstream_actor.price()
        self.cash.equation -= cashflow
        upstream_actor.cash.equation += cashflow
        return

    def connect_eggs(self, egg_supplier):
        flow = self.model.flow(f"{egg_supplier.name} to {self.name} Egg Flow")
        flow.equation = self.egg_demand
        self.eggs.equation += flow
        egg_supplier.eggs.equation -= flow
        return

    def volume_out(self):
        if self.downstream_actor is not None:
            volume_out = self.model.flow(
                f"{self.name} to {self.downstream_actor} Volume"
            )
            volume_out.equation = sd.min(
                self.supply,
                self.model.converter(f"{self.name} to {self.downstream_actor} Demand")
            )
            return volume_out
        else:
            return

    # cash
    def cash(self):
        cash = self.model.stock(f"{self.name} Cash")
        if self.upstream_actor is not None and self.downstream_actor is not None:
            cash.equation = (
                    self.cash_in()
                    - self.model.flow(f"{self.name} to {self.upstream_actor} Cashflow")
            )
        return cash

    def cash_in(self):
        if self.downstream_actor is not None:
            cash_in = self.model.flow(
                f"{self.downstream_actor} to {self.name} Cashflow"
            )
            cash_in.equation = self.price() * self.volume_out()
            return cash_in
        else:
            return

    def revenue(self):
        revenue = self.model.converter(f"{self.name} Revenue")
        revenue.equation = self.cash_in()
        return revenue

    def rev_fcast(self):
        rev_fcast = self.model.converter(f"{self.name} Revenue Forecast")
        rev_fcast.equation = self.revenue()
        return rev_fcast

    # price
    def price(self):
        price = self.model.converter(f"{self.name} Price")
        if self.upstream_actor is not None:
            upstream_price = self.model.converter(f"{self.upstream_actor} Price")
            price.equation = upstream_price * sd.delay(
                self.model,
                self.d2s_ratio(),
                30.0,
                initial_value=1.0
            )
        return price

    def d2s_ratio(self):
        d2s_ratio = self.model.converter(f"{self.name} Demand-to-Supply Ratio")
        d2s_ratio.equation = (
            self.model.converter(f"{self.name} to {self.downstream_actor} Demand") / self.supply
        )
        return d2s_ratio

    # demand
    def demand(self):
        if self.upstream_actor is not None:
            demand = self.model.converter(
                f"{self.upstream_actor} to {self.name} Demand"
            )
            demand.equation = self.rev_fcast() / self.price()
            return demand
        else:
            return


def set_model_logic(start_serial, stop_serial, df):
    """ Setup model based on start date, end date, and df containing input data """

    time_step_in_days = 2.0
    commodity = "Rice"

    model = Model(
        starttime=start_serial,
        stoptime=stop_serial,
        dt=1.0 * time_step_in_days,
    )

    # INITIALISE VARIABLES

    # DISPLACEMENT
    hp_pop = model.constant("Host Population")
    idp_pop, idp_pop_iv = create_model_stock(model, "IDP Population")
    aap_pop, aap_pop_iv = create_model_stock(model, "Affected Area Population")
    disp_rate = model.flow("Displacement Rate")
    ret_rate = model.flow("Return Rate")

    t_disp = model.constant("Displacement Time")
    t_ret = model.constant("Return Time")
    danger = model.converter("Perceived Danger")


    # FARMER
    # physical
    f_stock, f_stock_iv = create_model_stock(model, "Farmer Stock")
    f_prod = model.flow("Farmer Production")
    f2t_vol = model.flow("Farmer to Trader Volume")
    f_supply = model.converter("Farmer Supply")
    f2t_demand = model.converter("Farmer to Trader Demand")
    f2t_leadtime = model.constant("Farmer to Trader Leadtime")
    f_loss = model.flow("Farmer Loss Rate")
    t_f_loss = model.constant("Farmer Loss Time")
    # price
    baseline_price = model.constant("Baseline Price")
    f_ds_ratio = model.converter("Farmer Demand-to-Supply Ratio")
    f_price = model.converter("Farmer Price")
    # cash
    t2f_cashflow = model.flow("Trader to Farmer Cashflow")

    # TRADER
    # physical
    t_stock, t_stock_iv = create_model_stock(model, "Trader Stock")
    t2w_vol = model.flow("Trader to Wholesaler Volume")
    t_supply = model.converter("Trader Supply")
    t2w_leadtime = model.constant("Trader to Wholesaler Leadtime")
    # price
    t_ds_ratio = model.converter("Trader Demand-to-Supply Ratio")
    t_price = model.converter("Trader Price")
    # cash
    t_cash, t_cash_iv = create_model_stock(model, "Trader Cash")
    w2t_cashflow = model.flow("Wholesaler to Trader Cashflow")

    wholesaler = SupplyChainActor(
        model,
        "Wholesaler",
        upstream_actor="Trader",
        downstream_actor="Retailer"
    )

    retailer = SupplyChainActor(
        model,
        "Retailer",
        upstream_actor="Wholesaler",
        downstream_actor="Consumer"
    )

    retailer.connect_to_upstream(wholesaler)

    # CONSUMER
    hp_income_baseline = model.constant("Host Population Income Baseline")
    idp_income_baseline = model.constant("IDP Income Baseline")
    c_needs = model.constant(f"{commodity} Needs Per Capita")
    c_max_income_frac = model.constant(f"Maximum Fraction of Income Spent on {commodity}")
    hp_income = model.converter("Host Population Income")
    idp_income = model.converter("IDP Income")
    hp_pc_demand = model.converter("HP Per Capita Demand")
    idp_pc_demand = model.converter("IDP Per Capita Demand")
    hp_demand = model.converter("HP Demand")
    idp_demand = model.converter("IDP Demand")
    c_demand = model.converter("Retailer to Consumer Demand")

    # DATA
    data_prod_usda = create_model_data_variable(model, df, "Production (USDA)")
    data_deaths_ucdp = create_model_data_variable(model, df, "Deaths (UCDP)")
    data_ip_iom = create_model_data_variable(model, df, "IDP Population (IOM)")
    data_ruralinflation_nbs = create_model_data_variable(model, df, "Rural Inflation")

    # CONNECT STOCKS AND FLOWS

    # displacement
    idp_pop.equation = disp_rate - ret_rate
    aap_pop.equation = ret_rate - disp_rate

    # physical
    f_stock.equation = f_prod - f2t_vol - f_loss
    t_stock.equation = f2t_vol - t2w_vol

    # cash
    t_cash.equation = w2t_cashflow - t2f_cashflow

    # DEFINE THE REST

    # displacement
    danger.equation = smooth_model_variable(model, data_deaths_ucdp, 30.0, 0.0) / 90.0
    disp_rate.equation = aap_pop * danger / t_disp
    ret_rate.equation = idp_pop * (1.0 - danger) / t_ret

    # farmer
    f_prod.equation = data_prod_usda
    f2t_vol.equation = sd.min(f2t_demand, f_supply)
    f_ds_ratio.equation = f2t_demand / f_supply
    f_price.equation = baseline_price
    f2t_demand.equation = wholesaler.demand()
    f_supply.equation = f_stock / f2t_leadtime
    f_loss.equation = f_stock / t_f_loss

    # trader
    t2w_vol.equation = sd.min(wholesaler.demand(), t_supply)
    t_ds_ratio.equation = wholesaler.demand() / t_supply
    t_price.equation = f_price
    t_supply.equation = t_stock / t2w_leadtime
    t2f_cashflow.equation = f_price * f2t_vol
    w2t_cashflow.equation = t_price * t2w_vol


    # consumer
    hp_income.equation = hp_income_baseline
    idp_income.equation = idp_income_baseline
    hp_pc_demand.equation = sd.min(c_needs, hp_income * c_max_income_frac / wholesaler.price())
    hp_demand.equation = hp_pc_demand * hp_pop
    idp_pc_demand.equation = sd.min(c_needs, idp_income * c_max_income_frac / wholesaler.price())
    idp_demand.equation = idp_pc_demand * idp_pop
    c_demand.equation = hp_demand + idp_demand

    retailer.demand().equation = c_demand

    # CONSTANTS

    # initial values
    idp_pop_iv.equation = 1500000.0
    aap_pop_iv.equation = 1900000.0
    f_stock_iv.equation = 100000.0
    t_stock_iv.equation = 100000.0
    t_cash_iv.equation = 0.0

    wholesaler.stock.initial_value = 100000.0
    wholesaler.cash.initial_value = 0.0
    retailer.stock.initial_value = 100000.0
    retailer.cash.initial_value = 0.0

    # time constants
    t_disp.equation = 30.0
    t_ret.equation = 6.0 * 30.0
    t_f_loss.equation = 7.0

    # leadtimes
    f2t_leadtime.equation = 1.0
    t2w_leadtime.equation = 1.0
    wholesaler.leadtime.equation = 1.0
    retailer.leadtime.equation = 1.0

    # others
    baseline_price.equation = 200.0

    # consumer
    hp_pop.equation = 1000000.0
    c_max_income_frac.equation = 0.5
    c_needs.equation = 10.0 / 30.0
    hp_income_baseline.equation = 4000.0 / 30.0
    idp_income_baseline.equation = 2000.0 / 30.0

    retailer.connect_eggs(wholesaler)

    return model
