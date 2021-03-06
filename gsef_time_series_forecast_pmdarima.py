import timeit
start_time = timeit.default_timer()

## Import libraries
import time
import datetime
import pandas as pd
import io
import matplotlib.pyplot as plt

# GSEF forecast
gsef= pd.read_csv('gsef_output/historical_gsef.csv', parse_dates=['Date'], dayfirst=True)

#This analysis demonstrates the use of ARIMA models to predict the prices of the NN (L) Global Sustainable Equity fund.

## Imports & data loading
import pmdarima as pm
from pmdarima.model_selection import train_test_split
import numpy as np

gsef_selected= gsef[['Date','Close']]

y = gsef_selected['Close'].values

## Data splitting
train_data, test_data = gsef_selected[0:int(len(gsef_selected)*0.65)], gsef_selected[int(len(gsef_selected)*0.65):]

# Load/split your data
y_train, y_test = train_test_split(y, train_size= len(train_data))

## Pre-modeling analysis
from pandas.plotting import lag_plot

fig, axes = plt.subplots(3, 2, figsize=(12, 18))
plt.title('GSEF Autocorrelation plot')

# The axis coordinates for the plots
ax_idcs = [
    (0, 0),
    (0, 1),
    (1, 0),
    (1, 1),
    (2, 0),
    (2, 1)
]

for lag, ax_coords in enumerate(ax_idcs, 1):
    ax_row, ax_col = ax_coords
    axis = axes[ax_row][ax_col]
    lag_plot(gsef_selected['Close'], lag=lag, ax=axis)
    axis.set_title(f"Lag={lag}")

#plt.show()

## Estimating the differencing term
# An integrative term, d, is typically only used in the case of non-stationary data. Stationarity in a time series indicates that a series’ statistical attributes, such as mean, variance, 
# etc., are constant over time (i.e., it exhibits low heteroskedasticity).

# A stationary time series is far more easy to learn and forecast from. With the d parameter, we can force the ARIMA model to adjust for non-stationarity on its own, without having to worry 
# about doing so manually.

# To make our data stationary in the case of ARIMA models, we estimate the appropriate differencing (d) value, and we use the estimated differencing value to difference the time series 
# accordingly.

from pmdarima.arima import ndiffs

kpss_diffs = ndiffs(y_train, alpha=0.05, test='kpss', max_d=6)
adf_diffs = ndiffs(y_train, alpha=0.05, test='adf', max_d=6)
n_diffs = max(adf_diffs, kpss_diffs)

print(f"Estimated differencing value: {n_diffs}")

## Fitting our model
model = pm.auto_arima(y_train, d=n_diffs, seasonal=True, stepwise=True,
                     suppress_warnings=True, error_action="ignore", max_p=6,
                     max_order=None, trace=True)

## Updating the model
from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_squared_error
from pmdarima.metrics import smape
from math import sqrt

def forecast_one_step():
    fc, conf_int = model.predict(n_periods=1, return_conf_int=True)
    return (
        fc.tolist()[0],
        np.asarray(conf_int).tolist()[0])

forecasts = []
confidence_intervals = []

for new_ob in y_test:
    fc, conf = forecast_one_step()
    forecasts.append(fc)
    confidence_intervals.append(conf)

    # Updates the existing model with a small number of MLE steps
    model.update(new_ob)

print(f"Mean absolute error/deviation (MAE/MAD): {round(mean_absolute_error(y_test, forecasts), 2)}")

# Mean Absolute Percent
def mean_absolute_percent_error(y_test, forecasts): 
    return round(np.mean(np.abs((y_test - forecasts) / forecasts)), 2)

mape= round(mean_absolute_percent_error(y_test, forecasts), 2) #same as MAE but percentage
print(f"\nMean absolute percent error (MAPE):", round(mape, 2))

print(f"\nMean squared error: {round(mean_squared_error(y_test, forecasts), 2)}")

print(f"\nRoot mean squared error (RMSE): {round(sqrt(mean_squared_error(y_test, forecasts)), 2)}")

print(f"\nSMAPE: {round(smape(y_test, forecasts), 2)}")


model.summary()

## Viewing forecasts
fig, axes = plt.subplots(2, 1, figsize=(12, 12))

# --------------------- Actual vs. Predicted --------------------------
axes[0].plot(y_train, color='blue', label='Training Data')
axes[0].plot(test_data.index, forecasts, color='green', marker='o',
             label='Predicted Price')

axes[0].plot(test_data.index, y_test, color='red', label='Actual Price')
axes[0].set_title('GSEF Prices Forecast')
axes[0].set_xlabel('Dates')
axes[0].set_ylabel('Prices')


axes[0].legend()


# ------------------ Predicted with confidence intervals ----------------
axes[1].plot(y_train, color='blue', label='Training Data')
axes[1].plot(test_data.index, forecasts, color='green',
             label='Predicted Price')

axes[1].set_title('Prices Forecasts & Confidence Intervals')
axes[1].set_xlabel('Dates')
axes[1].set_ylabel('Prices')

conf_int = np.asarray(confidence_intervals)
axes[1].fill_between(test_data.index,
                     conf_int[:, 0], conf_int[:, 1],
                     alpha=0.9, color='orange',
                     label="Confidence Intervals")

axes[1].legend()

## Forecast the Price for the next 10 business days
# Forecast the Price for the next 10 business days
forecast= model.predict(start= len(gsef_selected), end= len(gsef_selected)+10, type= 'levels')

following_day= gsef_selected.Date.iloc[-1]+ pd.DateOffset(1)

index_future_dates= pd.date_range(start= following_day, periods=10, freq='B')

forecast_df = pd.DataFrame(forecast, columns = ['Forecasted Closing Price'], index= pd.DatetimeIndex(index_future_dates)).reset_index(level=0)

forecast_df.rename(columns={'index': 'Date'}, inplace=True)

existing_with_forecast= pd.concat([gsef_selected, forecast_df], ignore_index=True, sort=False)

## Append only new forecast data points to the existing ones and calculate the difference between the forecast and known closing prices

# Read the existing forecast
existing_forecast= pd.read_csv('gsef_output/gsef_forecast.csv', parse_dates=['Date'], dayfirst=True)

merged_forecast= pd.merge(existing_forecast, gsef_selected.rename(columns={'Close':'Closing Price'}), how= 'left', left_on='Date', right_on='Date')
merged_forecast["Closing Price_x"] = merged_forecast["Closing Price_x"].combine_first(merged_forecast["Closing Price_y"])

merged_forecast= merged_forecast.drop('Closing Price_y', axis=1)

#merged_forecast= merged_forecast.set_index('Date')

merged_forecast= merged_forecast.rename(columns={'Closing Price_x': 'Closing Price'}).sort_values(by="Date")

merged_forecast['Difference']= merged_forecast['Forecasted Closing Price'] - merged_forecast['Closing Price']

## Save the updated forecasts, real closing prices and the difference between the forecast and known closing price for the corresponding dates

# Output the appended forecast to a CSV file
merged_forecast.to_csv('gsef_output/gsef_forecast.csv', index=False)

## Visualise and save the forecasts

plt.figure(figsize=(14, 10))

plt.plot(existing_with_forecast['Date'][-10:], existing_with_forecast['Forecasted Closing Price'][-10:], color='dodgerblue')

#ax1.set_xticks(np.arange(len(existing_with_forecast['Date'][-10:])))

#plt.yticks(np.arange(existing_with_forecast['Close'][-10:]))

plt.ylabel('Forecasted Price')

plt.title('GSEF 10 Business Days Forecast')

forecast_chart= 'gsef_output/gsef_10_day_forecast.png'

import os
if os.path.exists(forecast_chart):
  os.remove(forecast_chart)
else:
  print("The Forecast chart didn't exist and it has been created.")

plt.savefig('gsef_output/gsef_10_day_forecast.png', dpi=100)

#plt.show()

## Time Elapsed
# Calculate and print the time elapsed to run ETL process and the date and time of the latest run
time_elapsed = timeit.default_timer() - start_time

time_elapsed_minutes = int((time_elapsed % 3600) // 60)

time_elapsed_seconds = int(time_elapsed % 60)

now = datetime.datetime.now()

print("\nSuccess! Your GSEF forecast has been updated in {} minutes and {} seconds on {}".format(time_elapsed_minutes, time_elapsed_seconds, now.strftime("%Y-%m-%d %H:%M:%S")))