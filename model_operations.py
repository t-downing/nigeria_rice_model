import BPTK_Py
from model_config2 import set_model_logic
from datetime import datetime
from general_functions import *


def setup_model(start_date, end_date, df, checking=False):
    start_serial, end_serial = datetime_to_serial([start_date, end_date])
    model = set_model_logic(start_serial, end_serial, df)
    if checking:
        print("checking constants . . . ")
        for variable in model.constants:
            if not isinstance(model.evaluate_equation(variable, start_serial), float):
                print(f"{variable} is not a float!")

        print("checking equations for: ")
        print("stocks . . . ")
        for variable in model.stocks:
            if model.stock(variable).equation is None:
                print(f"The stock '{variable}' does not have an equation!")
        print("flows . . . ")
        for variable in model.flows:
            if model.flow(variable).equation is None:
                print(f"The flow '{variable}' does not have an equation!")
        print("converters . . . ")
        for variable in model.converters:
            if model.converter(variable).equation is None:
                print(f"The converter '{variable}' does not have an equation!")
        print("constants . . . ")
        for variable in model.constants:
            if model.constant(variable).equation is None:
                print(f"The constant '{variable}' does not have an equation!")
        variables = (
                [str(var) for var in model.stocks]
                + [str(var) for var in model.flows]
                + [str(var) for var in model.converters]
                + [str(var) for var in model.constants]
        )
        for variable in variables:
            print(f"eval eq for {variable}")
            if not isinstance(model.evaluate_equation(variable, start_serial), float):
                print(f"The variable '{variable}' has an equation "
                      "but it does not evaluate!")
            if not isinstance(model.evaluate_equation(variable, start_serial+10), float):
                print(f"The variable '{variable}' has an equation "
                      "but it does not evaluate past 10 iterations!")
    model_env = BPTK_Py.bptk()
    model_env.register_model(model)
    scenario_manager = {
        "scenario_manager": {
            "model": model
        }
    }
    model_env.register_scenario_manager(scenario_manager)
    return model_env, model


def run_model(model_env, model, scenario_name, constants, start_date, stop_date):
    """ Run model with constants and dates, output df of results """

    # set dates
    model.starttime = datetime_to_serial(start_date)
    model.stoptime = datetime_to_serial(stop_date)

    # register scenario
    model_env.register_scenarios(
        scenarios={
            scenario_name: {
                "constants": constants
            },
        },
        scenario_manager="scenario_manager"
    )

    # choose variables to output
    output_variables = [str(var) for var in model.stocks] \
        + [str(var) for var in model.flows] \
        + [str(var) for var in model.converters] \
        # + [str(var) for var in model.constants]
    excluded_strings = ["bptk", "SMOOTH", "Zero Flow"]
    for excluded_string in excluded_strings:
        output_variables = [
            variable for variable in output_variables if not excluded_string in variable
        ]

    # run model
    df = model_env.plot_scenarios(
        scenarios=scenario_name,
        scenario_managers="scenario_manager",
        equations=output_variables,
        return_df=True
    ).reset_index()

    # clean up df
    df["Scenario"] = scenario_name
    df["Date"] = serial_to_datetime(df["t"])
    df["t_check"] = datetime_to_serial(df["Date"])
    return df




