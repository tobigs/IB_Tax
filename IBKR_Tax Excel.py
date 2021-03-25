# %% [markdown]
# # IBKR Tax

# %%
import pandas as pd


# %%
from currency_converter import CurrencyConverter
c = CurrencyConverter(fallback_on_missing_rate=True)

# %% [markdown]
# # Read Data
# %% [markdown]
# Requirements:
# - English activity statement
# - Year of activity statement 2020 and older

# %%
myfile = "MY_ACTIVITY_STATEMENT.csv"
myfile = "data/test.csv"

# %% [markdown]
# https://stackoverflow.com/questions/27020216/import-csv-with-different-number-of-columns-per-row-using-pandas/57824142#57824142

# %%
### Loop the data lines
with open(myfile, 'r') as temp_f:
    # get No of columns in each line
    col_count = [ len(l.split(",")) for l in temp_f.readlines() ]

### Generate column names  (names will be 0, 1, 2, ..., maximum columns - 1)
column_names = [i for i in range(0, max(col_count))]

### Read csv
df = pd.read_csv(myfile, header=None, delimiter=",", names=column_names)

# %% [markdown]
# # Trades

# %%
df_trades = df[df.iloc[:,0] == "Trades"].dropna(how='all', axis=1)
df_trades, df_trades.columns = df_trades.iloc[1:] , df_trades.iloc[0]
df_trades.columns.name = None


# %%
# obtain asset type
try:
    df_trades[['Asset','Category']] = df_trades["Asset Category"].str.split("-", expand=True).copy()
except:
    df_trades["Asset"] = df_trades["Asset Category"]

# remove subheader
df_trades = df_trades[(df_trades["Realized P/L"]!="Realized P/L") & ~(df_trades["Header"].str.contains("SubTotal|Total"))].copy()

# convert dtypes
df_trades["Realized P/L"] = df_trades["Realized P/L"].astype(float)

# remove empty rows
df_trades = df_trades[df_trades["Realized P/L"].notnull()] #df_trades["Realized P/L"]!=0) & 

 
# convert to datetime
df_trades["Date/Time"] = pd.to_datetime(df_trades["Date/Time"],  infer_datetime_format=True)

df_trades = df_trades.reset_index(drop=True)


# %%
# convert to EUR using ECB rates
df_trades["P/L [€]"] = df_trades.apply(lambda row: c.convert(
    row["Realized P/L"] , row.Currency, date=row["Date/Time"]), axis=1)
df_trades["P [€]"] = df_trades["P/L [€]"].apply(lambda row: row if row > 0 else 0)
df_trades["L [€]"] = df_trades["P/L [€]"].apply(lambda row: row if row < 0 else 0)


# %%
PL_TradesDet = df_trades.groupby(["Currency", "Asset"]).sum()
PL_Trades = df_trades.groupby(["Asset"]).sum()

# %% [markdown]
# # P/L Forex

# %% [markdown]
# ## Not fully tested

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

# %% [markdown]
# # Dividend

# %%
def process_df(df):
    # set first row as header
    df, df.columns = df.iloc[1:] , df.iloc[0]
    
    # remove rows with sum
    df = df[~df.Currency.str.contains("Total")]
    
    # conver dtypes
    df["Amount"] = df["Amount"].astype(float)
    
    # convert to datetime
    df["Date"] = pd.to_datetime(df["Date"],  infer_datetime_format=True)
    
    # convert to EUR using ECB rates
    df["Amount [€]"] = df.apply(lambda row: c.convert(row["Amount"] , row["Currency"], date=row["Date"]), axis=1)
    
    # label CFD dividens
    df["Description"] = df["Description"].str.replace(" ","")
    df[['Symbol','TrashCol']] = df["Description"].str.split("(", n=1, expand=True).copy()
    df[['Country','TrashCol']] = df["TrashCol"].str.split(")", n=1, expand=True).copy()
    df["Country"] = df["Country"].str.extract(r'(^\D+)').fillna("CFD")
    df["Asset"] = "Stocks"
    df.loc[df.Symbol.str.endswith("n"), "Asset"] = "CFDs" 
    
    # remove index from column names
    df.columns.name = None
    df.reset_index(drop=True)
    
    return df


# %%
df_div = df[df.iloc[:,0] == "Dividends"].dropna(how='all', axis=1)
df_wtax = df[df.iloc[:,0] == "Withholding Tax"].dropna(how='all', axis=1)
df_871 = df[df.iloc[:,0] == "871(m) Withholding"].dropna(how='all', axis=1)


# %%
df_div = process_df(df_div)
df_wtax = process_df(df_wtax) if not df_wtax.empty else df_wtax


# %%
df_871 = process_df(df_871) if not df_871.empty else df_871
df_871["Asset"] = "CFDs"
df_wtax = df_wtax.append(df_871)


# %%
WithholdingTax = df_wtax.groupby(["Currency", "Asset", "Country"]).sum() if not df_871.empty else df_871
Dividends = df_div.groupby(["Currency", "Asset", "Country"]).sum()

# %% [markdown]
# # Results

# %%
WithholdingTax.to_excel("WithholdingTax.xlsx") if not df_871.empty else "No Withholding Tax"


# %%
Dividends.to_excel("Dividends.xlsx")


# %%
PL_Trades.to_excel("PL_Trades.xlsx")


# %%
PL_TradesDet.to_excel("PL_TradesDet.xlsx")


# %%



# %%



