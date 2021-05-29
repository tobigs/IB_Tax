# %% [markdown]
# # IBKR Tax

# %% [markdown]
# Requirements:
# - English activity statement
# - Year of activity statement 2020 and older
# - All Options, Futures, CFDs closed before year end
# - Only single short put and short call (Line 25 Losses from the disposal of worthless assets as per section 20(1) of the Income Tax Act not implemented)
# - Manual credit of Withholding tax
# - No classification of REITs as investment fund required
# %%
import pandas as pd

from IPython.display import display

from utils import *

# %% [markdown]
# # Read Data
# %%

myFile = "MY_ACTIVITY_STATEMENT.csv"
myFile = "Data/ibkr/main_2020.csv"

df = parse_activityStatement(myFile)

# %% [markdown]
# # Trades
# %%

tradesStatement = get_trades(df)

PL_Trades = tradesStatement.pl
PL_TradesDet = tradesStatement.plDet

df_trades = tradesStatement.trades
df_futures = tradesStatement.futures
df_options = tradesStatement.options
df_cfd = tradesStatement.cfd

display(PL_TradesDet, PL_Trades)

# %% [markdown]
# # Dividend
# %%

WithholdingTax, Dividends = get_dividends(df)

display(WithholdingTax, Dividends)

# %% [markdown]
# # Interest
# %%

Interest = get_interest(df)

Interest

# %% [markdown]
# # Futures / Option / CFD Profit and Loss
# %% [markdown]
# - Only applies if every position is closed and opened during the year (i.e. Options)
# %%

multiplier = 1
Futures, FuturesDet = getTradesPnl(df_futures.copy(), multiplier)

display(Futures, FuturesDet)

# %%
multiplier = 100
Options, OptionsDet = getTradesPnl(df_options.copy(), multiplier)

display(Options, OptionsDet)


# %%
multiplier = 1
Cfd, CfdDet = getTradesPnl(df_cfd.copy(), multiplier)

display(Cfd, CfdDet)

# %% [markdown]
# # Anlage KAP

activityStatement = namedtuple('statement', ['pl', 'plDet', 'options', 'optionsDet', 'dividends', 'interest'])

KAP = get_kap(activityStatement(PL_Trades, PL_TradesDet, Options, OptionsDet, Dividends, Interest))

KAP

# %% [markdown]
# # Results

# %% Add sum row
WithholdingTax = addSumRow(WithholdingTax)
Dividends = addSumRow(Dividends)
Interest = addSumRow(Interest)
PL_Trades = addSumRow(PL_Trades)
PL_TradesDet = addSumRow(PL_TradesDet)
OptionsDet = addSumRow(OptionsDet) if not OptionsDet.empty else OptionsDet
FuturesDet = addSumRow(FuturesDet) if not FuturesDet.empty else FuturesDet
CfdDet = addSumRow(CfdDet) if not CfdDet.empty else CfdDet
# %%
Interest

# %%
WithholdingTax if not WithholdingTax.empty else "No Withholding Tax"

# %%
Dividends

# %%
PL_Trades

# %%
PL_TradesDet

# %% [markdown]
# # Detailed Results

# %%
display(Options, OptionsDet)

# %%
display(Futures, FuturesDet)

# %%
display(Cfd, CfdDet)

# %% [markdown]
# ---
# %% [markdown]
# # P/L Forex
# %% [markdown]
# ## Experimental stuff 
# Not fully tested
# %% [markdown]
# ### Only applies if every position is closed and opened during the year (i.e. Options)
# %% [markdown]
# Use > Realized & Unrealized Performance Summary > Forex

# %%
assets  = df_trades.Asset.unique()
results = []
for asset in assets:
    try:
        df_asstes = df_trades[df_trades.Asset == asset].copy()
        df_asstes["Basis"] = df_asstes["Basis"].astype(float)
        df_asstes["Basis [€]"] = df_asstes.apply(lambda row: c.convert(
            row["Basis"] , row.Currency, date=row["Date/Time"]), axis=1)
        currencies = df_asstes.Currency.unique()
        
        for curr in currencies:
            df_curr = df_asstes[df_asstes.Currency==curr].copy()
            open_position = df_curr["Basis"].round(2).sum()
            pl_forex = df_curr["Basis [€]"].round(2).sum()
            avg_rate = df_asstes.apply(lambda row: c.convert(
            1 , row.Currency, date=row["Date/Time"]), axis=1).mean()
            results.append([curr, avg_rate, pl_forex, open_position, asset])
            #results.append([curr, pl_forex, open_position, asset])
            
    except Exception as e:
        print(f"Failed for {asset} with error: {e}")
df_forex = pd.DataFrame(results).T
df_forex, df_forex.columns = df_forex.iloc[1:] , df_forex.iloc[0]
df_forex = df_forex.T
df_forex.columns = ["Average Rate", "PL_Forex [€]", "Open Position", "Asset"]
#df_forex.columns = ["PL_Forex [€]", "Open Position", "Asset"]
df_forex.index.name = None
df_forex["PL_Forex_ADJ [€]"] = df_forex["PL_Forex [€]"] - df_forex["Open Position"]
df_forex.loc[:,:] = df_forex.loc[:,:].apply(pd.to_numeric, errors = 'ignore')
df_forex.loc['Column_Total'] = df_forex.sum(numeric_only=True, axis=0)
PL_Forex = df_forex
PL_Forex