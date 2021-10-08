import hdx.hdx_configuration
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime

from hdx.utilities.easy_logging import setup_logging
from hdx.hdx_configuration import Configuration
from hdx.data.dataset import Dataset


def import_all_data():
    """ Read all data from CSV files and store in one df
    Units must be: kg, day, NGN, USD, single death
    """
    df = pd.DataFrame()
    df = pd.concat([df, read_vam("Rice (local)", "Maiduguri", "Price (VAM)")], axis=1)
    df = pd.concat([df, read_nbs_inflation([
        "Food Inflation", "Transport Inflation", "Rural Inflation"
    ])], axis=1)
    df = pd.concat([df, read_ucdp_conflict("Deaths (UCDP)")], axis=1)
    df = pd.concat([df, read_usda("Production (USDA)")], axis=1)
    df = pd.concat([df, read_iom("IDP Population (IOM)")], axis=1)
    return df.sort_index()


def download_all_data():
    """ Download all recent datasets and save them as CSVs """
    download_from_hdx("wfp-food-prices-for-nigeria")
    download_from_hdx("faostat-prices-for-nigeria")
    return


def download_from_hdx(hdx_name, resource_number=0):
    """ Download most recent dataset from HDX and save as CSV """
    setup_logging()
    try:
        Configuration.create(hdx_site='prod', user_agent='SD_model_demo', hdx_read_only=True)
    except hdx.hdx_configuration.ConfigurationError:
        pass
    dataset = Dataset.read_from_hdx(hdx_name)
    resources = dataset.get_resources()
    url = resources[resource_number]["download_url"]
    filename = url[url.rfind("/")+1:]
    df = pd.read_csv(url)
    path = f"data/{filename}"
    df.to_csv(path)
    return


def read_vam(commodities, market, output_col):
    """ Read VAM data from CSV and output df """
    filename = "data/wfp_food_prices_nga.csv"
    df = pd.read_csv(filename, skiprows=[1])
    df["Date"] = pd.to_datetime(df["date"])

    # pick commodity
    # all_commodities = df["commodity"].unique()
    # print(all_commodities)
    try:
        df = df[df["commodity"].isin(commodities)]
    except TypeError:
        df = df[df["commodity"] == commodities]

    # # pick market
    # print(df["market"].unique())
    df = df[df["market"] == market]

    # correct units
    def price_to_kg_price(unit, price):
        index = unit.find("KG")
        if index == 0 or index == -1:
            kgs = 1.0
        else:
            kgs = float(unit[:index-1])
        return price / kgs
    df["unit-price"] = df["price"].copy()
    df["price"] = df.apply(lambda x: price_to_kg_price(x["unit"], x["price"]), axis=1)

    df.rename(columns={"price": output_col}, inplace=True)
    df = df.groupby(pd.Grouper(key="Date", freq="D"))[output_col].mean().dropna().reset_index()
    df = df[["Date", output_col]].set_index("Date")
    return df


def read_fao_inflation(type, output_col):
    # read file and set date
    filename = "data/consumer-price-indices_nga.csv"
    df = pd.read_csv(filename, skiprows=[1])
    df["Date"] = pd.to_datetime(df["StartDate"])
    # filter df
    print(df.columns)
    print(df["Item"].unique())
    df = df[df["Item"] == type]
    # correct naming
    df.rename(columns={"Value": output_col}, inplace=True)
    # select single column
    df = df[["Date", output_col]].set_index("Date")
    return df


def read_nbs_inflation(output_cols):
    filename = "data/cpi_1NewJULY2021.xlsx"
    sheet_start, sheet_stop = '1995-01-01', '2021-07-01'
    dates = pd.date_range(sheet_start, sheet_stop, freq='MS')

    df = pd.read_excel(filename, skiprows=range(4), sheet_name='Table1')
    df.index = dates
    both_food = df.iloc[:, 12]

    df = pd.read_excel(filename, skiprows=[0, 2], sheet_name='Table2')
    df.index = dates
    both_transport = df.loc[:, 'Transport']

    df = pd.read_excel(filename, skiprows=[0, 2], sheet_name='Table3')
    df.index = dates
    rural_all = df.loc[:, 'All Items']

    df = pd.concat([both_food, both_transport, rural_all], axis=1)
    df.columns = output_cols
    df.index.name = "Date"
    return df


def read_ucdp_conflict(output_col="Deaths (UCDP)"):
    filename = "data/conflict_data_nga.csv"
    df = pd.read_csv(filename, skiprows=[1])
    df["Date"] = pd.to_datetime(df["date_start"])
    adm_1 = "Borno state"
    df = df[df["adm_1"] == adm_1]
    df = df.groupby(pd.Grouper(key="Date", freq="D"))["best"].sum().reset_index()
    df.rename(columns={"best": output_col}, inplace=True)
    df = df.set_index("Date")
    return df


def read_usda(output_col="Production (USDA)"):
    """ Output seasonal production (one value for each month
    Note: does not actually read CSV, values are stored in this function
    """
    # production MT per year
    data = np.array([3782, 3941, 4536, 4470, 4538, 5040, 4890, 5000])
    # production kg per day
    data = data * 1000000 / 365
    dates = pd.date_range('2014-01-01', '2021-01-01', freq='YS')
    df = pd.DataFrame(data=data, index=dates, columns=[output_col])
    df.index.name = "Date"

    # add seasonality
    dfo = df.resample('MS').ffill()
    data = np.tile(np.array([[0.045454545, 0, 0.045454545, 0.090909091, 0.090909091,
                              0.045454545, 0, 0.060606061, 0.106060606, 0.151515152,
                              0.181818182, 0.181818182]]), 10).T * 12
    dates = pd.date_range('2014-01-01', '2021-01-01', freq='MS')
    data = data[0:len(dates)]
    dfo['Seasonality'] = pd.DataFrame(data, index=dates)
    dfo[output_col] = dfo['Seasonality'] * dfo[output_col]
    return dfo[output_col]


def read_iom(output_col="IDP Population (IOM)"):
    """ Note: doesn't actually read HDX files, just reads previously processed sheet
    """
    filename = "data/_IOM compile.xlsx"
    df = pd.read_excel(filename)
    df.index = pd.to_datetime(df["Date"])
    df[output_col] = df["IDPs"]
    last_date = "2021-03-01"
    df = df.loc[:last_date]
    return df[output_col]
