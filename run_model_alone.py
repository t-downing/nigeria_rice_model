import pandas as pd
import BPTK_Py
import plotly.express as px
import plotly.graph_objects as go
from model_operations import *
from datetime import datetime
from import_data import *
import sys
import time

#sys.setrecursionlimit(10**6)

# read data into df
tic = time.time()
df_input = import_all_data()
toc = time.time()
print(f"data read took {round(toc - tic, 3)}s")

# setup model
start_date, stop_date = datetime(2015, 1, 1), datetime(2015, 3, 1)
tic = time.time()
model_env, model = setup_model(start_date, stop_date, df_input, checking=True)
toc = time.time()
print(f"setup took {round(toc - tic, 3)}s")

# run base scenario
tic = time.time()
df = pd.DataFrame
df = run_model(model_env, model, "base", {}, start_date, stop_date)
toc = time.time()
print(f"run took {round(toc - tic, 3)}s")
df = df.drop(columns=["Scenario", "t", "t_check"]).set_index("Date")

px.line(df, log_y=False).show()

fig = go.Figure(
    data=[
        go.Sankey(
            node=dict(label=["Trader", "Wholesaler", "Retailer"]),
            link=dict(
                source=[0, 1],
                target=[1, 2],
                value=[
                    df.iloc[-1]["Trader to Wholesaler Volume"],
                    df.iloc[-1]["Wholesaler to Retailer Volume"]
                ]
            )
        )
    ]
)

fig.show()


