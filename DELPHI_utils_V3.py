# Authors: Hamza Tazi Bouardi (htazi@mit.edu), Michael L. Li (mlli@mit.edu), Omar Skali Lami (oskali@mit.edu)
import pandas as pd
import numpy as np
import scipy.stats
import os
from datetime import datetime, timedelta
from typing import Union
from copy import deepcopy
from itertools import compress
import json
from DELPHI_params_V3 import (TIME_DICT, MAPPING_STATE_CODE_TO_STATE_NAME, default_policy,
                           default_policy_enaction_time, future_policies)
import boto3
from botocore.exceptions import ClientError

class DELPHIDataSaver:
    def __init__(
            self, path_to_folder_danger_map: str,
            path_to_website_predicted: str,
            df_global_parameters: Union[pd.DataFrame, None],
            df_global_predictions_since_today: pd.DataFrame,
            df_global_predictions_since_100_cases: pd.DataFrame,
    ):
        self.PATH_TO_FOLDER_DANGER_MAP = path_to_folder_danger_map
        self.PATH_TO_WEBSITE_PREDICTED = path_to_website_predicted
        self.df_global_parameters = df_global_parameters
        self.df_global_predictions_since_today = df_global_predictions_since_today
        self.df_global_predictions_since_100_cases = df_global_predictions_since_100_cases

    def save_all_datasets(self, save_since_100_cases=False, website=False):
        today_date_str = "".join(str(datetime.now().date()).split("-"))
        # Save parameters
        self.df_global_parameters.to_csv(
            self.PATH_TO_FOLDER_DANGER_MAP + f"/predicted/Parameters_Global_V2_{today_date_str}.csv", index=False
        )
        # Save predictions since today
        self.df_global_predictions_since_today.to_csv(
            self.PATH_TO_FOLDER_DANGER_MAP + f"/predicted/Global_V2_{today_date_str}.csv", index=False
        )
        if website:
            self.df_global_parameters.to_csv(
                self.PATH_TO_WEBSITE_PREDICTED + f"data/predicted/Parameters_Global_V2_{today_date_str}.csv",
                index=False
            )
            self.df_global_predictions_since_today.to_csv(
                self.PATH_TO_WEBSITE_PREDICTED + f"data/predicted/Global_V2_{today_date_str}.csv",
                index=False
            )
            self.df_global_predictions_since_today.to_csv(
                self.PATH_TO_WEBSITE_PREDICTED + f"data/predicted/Global.csv",
                index=False
            )
        if save_since_100_cases:
            # Save predictions since 100 cases
            self.df_global_predictions_since_100_cases.to_csv(
                self.PATH_TO_FOLDER_DANGER_MAP + f"/predicted/Global_V2_since100_{today_date_str}.csv", index=False
            )
            if website:
                self.df_global_predictions_since_100_cases.to_csv(
                    self.PATH_TO_WEBSITE_PREDICTED + f"data/predicted/Global_V2_since100_{today_date_str}.csv",
                    index=False
                )

    @staticmethod
    def create_nested_dict_from_final_dataframe(df_predictions: pd.DataFrame) -> dict:
        dict_all_results = {
            continent: {} for continent in df_predictions.Continent.unique()
        }
        for continent in dict_all_results.keys():
            countries_in_continent = list(df_predictions[df_predictions.Continent == continent].Country.unique())
            dict_all_results[continent] = {country: {} for country in countries_in_continent}

        keys_country_province = list(set([
            (continent, country, province) for continent, country, province in
            zip(df_predictions.Continent.tolist(), df_predictions.Country.tolist(), df_predictions.Province.tolist())
        ]))
        for continent, country, province in keys_country_province:
            df_predictions_province = df_predictions[
                (df_predictions.Country == country) & (df_predictions.Province == province)
            ].reset_index(drop=True)
            # The first part contains only ground truth value, so it doesn't matter which
            # policy/enaction time we choose to report these values
            dict_all_results[continent][country][province] = {
                "Day": sorted(list(df_predictions_province.Day.unique())),
                "Total Detected True": df_predictions_province[
                    (df_predictions_province.Policy == default_policy)
                    & (df_predictions_province.Time == default_policy_enaction_time)
                    ].sort_values("Day")["Total Detected True"].tolist(),
                "Total Detected Deaths True": df_predictions_province[
                    (df_predictions_province.Policy == default_policy)
                    & (df_predictions_province.Time == default_policy_enaction_time)
                    ].sort_values("Day")["Total Detected Deaths True"].tolist(),
            }
            dict_all_results[continent][country][province].update({
                policy: {
                    policy_enaction_time: {
                        "Total Detected": df_predictions_province[
                            (df_predictions_province.Policy == policy)
                            & (df_predictions_province.Time == policy_enaction_time)
                        ].sort_values("Day")["Total Detected"].tolist(),
                        "Total Detected Deaths": df_predictions_province[
                            (df_predictions_province.Policy == policy)
                            & (df_predictions_province.Time == policy_enaction_time)
                        ].sort_values("Day")["Total Detected Deaths"].tolist(),
                    }
                    for policy_enaction_time in df_predictions_province.Time.unique()
                }
                for policy in df_predictions_province.Policy.unique()
            })

        return dict_all_results

    def save_policy_predictions_to_dict_pickle(self, website=False, local_delphi=False):
        today_date_str = "".join(str(datetime.now().date()).split("-"))
        dict_predictions_policies_world_since_100_cases = DELPHIDataSaver.create_nested_dict_from_final_dataframe(
            self.df_global_predictions_since_100_cases
        )
        with open(
                self.PATH_TO_FOLDER_DANGER_MAP +
                f'/predicted/world_Python_{today_date_str}_Scenarios_since_100_cases.json', 'w'
        ) as handle:
            json.dump(dict_predictions_policies_world_since_100_cases, handle)

        with open(
                self.PATH_TO_FOLDER_DANGER_MAP + f'/predicted/world_Python_Scenarios_since_100_cases.json', 'w'
        ) as handle:
            json.dump(dict_predictions_policies_world_since_100_cases, handle)

        if local_delphi:
            with open(
                    f'./world_Python_{today_date_str}_Scenarios_since_100_cases.json', 'w'
            ) as handle:
                json.dump(dict_predictions_policies_world_since_100_cases, handle)

        if website:
            with open(
                self.PATH_TO_WEBSITE_PREDICTED +
                f'assets/policies/World_Scenarios.json', 'w'
            ) as handle:
                json.dump(dict_predictions_policies_world_since_100_cases, handle)

            # with open(
            #         self.PATH_TO_WEBSITE_PREDICTED + f'/data/predicted/world_Python_Scenarios_since_100_cases.json', 'w'
            # ) as handle:
            #     json.dump(dict_predictions_policies_world_since_100_cases, handle)


class DELPHIDataCreator:
    def __init__(
            self, x_sol_final: np.array, date_day_since100: datetime,
            best_params: np.array, continent: str, country: str, province: str,
            testing_data_included: bool = False,
    ):
        if testing_data_included:
            assert len(best_params) == 14,  f"Expected 9 best parameters, got {len(best_params)}"
        else:
            assert len(best_params) == 11, f"Expected 7 best parameters, got {len(best_params)}"
        self.x_sol_final = x_sol_final
        self.date_day_since100 = date_day_since100
        self.best_params = best_params
        self.continent = continent
        self.country = country
        self.province = province
        self.testing_data_included = testing_data_included

    def create_dataset_parameters(self, mape) -> pd.DataFrame:
        if self.testing_data_included:
            print(f"Parameters dataset created without the testing data parameters" +
                  " beta_0, beta_1: code will have to be modified")
        df_parameters = pd.DataFrame({
            "Continent": [self.continent], "Country": [self.country], "Province": [self.province],
            "Data Start Date": [self.date_day_since100], "MAPE": [mape], "Infection Rate": [self.best_params[0]],
            "Median Day of Action": [self.best_params[1]], "Rate of Action": [self.best_params[2]],
            "Rate of Death": [self.best_params[3]], "Mortality Rate": [self.best_params[4]],"Rate of Mortality Rate Decay": [self.best_params[5]],
            "Internal Parameter 1": [self.best_params[6]], "Internal Parameter 2": [self.best_params[7]]  ,
                        "Jump Magnitude": [self.best_params[8]], "Jump Time": [self.best_params[9]] ,
                                    "Jump Decay": [self.best_params[10]]
        })
        return df_parameters

    def create_df_backtest_performance_tuple(
            self,
            fitcasesnd,
            fitcasesd,
            testcasesnd,
            testcasesd,
            n_days_fitting,
            n_days_test,
    ):
        # Cases Train
        mae_train_nondeath, mape_train_nondeath = mae_and_mape(fitcasesnd, self.x_sol_final[15, :len(fitcasesnd)])
        mse_train_nondeath = mse(fitcasesnd, self.x_sol_final[15, :len(fitcasesnd)])
        sign_mape_train_nondeath = sign_mape(fitcasesnd, self.x_sol_final[15, :len(fitcasesnd)])
        # Deaths Train
        mae_train_death, mape_train_death = mae_and_mape(fitcasesd, self.x_sol_final[14, :len(fitcasesd)])
        mse_train_death = mse(fitcasesd, self.x_sol_final[14, :len(fitcasesd)])
        sign_mape_train_death = sign_mape(fitcasesd, self.x_sol_final[14, :len(fitcasesd)])
        # Cases Test
        mae_test_nondeath, mape_test_nondeath = mae_and_mape(testcasesnd, self.x_sol_final[15, -len(testcasesnd):])
        mse_test_nondeath = mse(testcasesnd, self.x_sol_final[15, -len(testcasesnd):])
        sign_mape_test_nondeath = sign_mape(testcasesnd, self.x_sol_final[15, -len(testcasesnd):])
        # Deaths Test
        mae_test_death, mape_test_death = mae_and_mape(testcasesd, self.x_sol_final[14, -len(testcasesd):])
        mse_test_death = mse(testcasesd, self.x_sol_final[14, -len(testcasesd):])
        sign_mape_test_death = sign_mape(testcasesd, self.x_sol_final[14, -len(testcasesd):])
        # MAPE on Daily Delta since last day of training for Cases
        true_last_train_cases = fitcasesnd[-1]
        pred_last_train_cases = self.x_sol_final[15, len(fitcasesnd)-1]
        mape_daily_delta_cases = mape_daily_delta_since_last_train(
            true_last_train_cases,
            pred_last_train_cases,
            testcasesnd,
            self.x_sol_final[15, -len(testcasesnd):]
        )
        # MAPE on Daily Delta since last day of training for Deaths
        true_last_train_deaths = fitcasesd[-1]
        pred_last_train_deaths = self.x_sol_final[14, len(fitcasesd) - 1]
        mape_daily_delta_deaths = mape_daily_delta_since_last_train(
            true_last_train_deaths,
            pred_last_train_deaths,
            testcasesd,
            self.x_sol_final[14, -len(testcasesd):]
        )
        # Create dataframe with all metrics
        df_backtest_performance_tuple = pd.DataFrame({
            "continent": [self.continent],
            "country": [self.country],
            "province": [self.province],
            "train_start_date": [(self.date_day_since100)],
            "train_end_date": [self.date_day_since100 + timedelta(days=n_days_fitting - 1)],
            "train_mape_cases": [mape_train_nondeath],
            "train_mape_deaths": [mape_train_death],
            "train_sign_mpe_cases": [sign_mape_train_nondeath],
            "train_sign_mpe_deaths": [sign_mape_train_death],
            "train_mae_cases": [mae_train_nondeath],
            "train_mae_deaths": [mae_train_death],
            "train_mse_cases": [mse_train_nondeath],
            "train_mse_deaths": [mse_train_death],
            "test_start_date": [self.date_day_since100 + timedelta(days=n_days_fitting)],
            "test_end_date": [self.date_day_since100 + timedelta(days=n_days_fitting + n_days_test - 1)],
            "test_mape_cases": [mape_test_nondeath],
            "test_mape_deaths": [mape_test_death],
            "test_sign_mpe_cases": [sign_mape_test_nondeath],
            "test_sign_mpe_deaths": [sign_mape_test_death],
            "test_mae_cases": [mae_test_nondeath],
            "test_mae_deaths": [mae_test_death],
            "test_mse_cases": [mse_test_nondeath],
            "test_mse_deaths": [mse_test_death],
            "mape_daily_delta_cases": [mape_daily_delta_cases],
            "mape_daily_delta_deaths": [mape_daily_delta_deaths],
        })
        for col in ["train_start_date", "train_end_date", "test_start_date", "test_end_date"]:
            df_backtest_performance_tuple[col] = df_backtest_performance_tuple[col].apply(lambda x: str(x.date()))

        return df_backtest_performance_tuple

    def create_datasets_predictions(self) -> (pd.DataFrame, pd.DataFrame):
        n_days_btw_today_since_100 = (datetime.now() - self.date_day_since100).days
        n_days_since_today = self.x_sol_final.shape[1] - n_days_btw_today_since_100
        all_dates_since_today = [
            str((datetime.now() + timedelta(days=i)).date())
            for i in range(n_days_since_today)
        ]
        # Predictions
        total_detected = self.x_sol_final[15, :]  # DT
        total_detected = [int(round(x, 0)) for x in total_detected]
        active_cases = (
                self.x_sol_final[4, :] + self.x_sol_final[5, :] + self.x_sol_final[7, :] + self.x_sol_final[8, :]
        )  # DHR + DQR + DHD + DQD
        active_cases = [int(round(x, 0)) for x in active_cases]
        active_hospitalized = self.x_sol_final[4, :] + self.x_sol_final[7, :]  # DHR + DHD
        active_hospitalized = [int(round(x, 0)) for x in active_hospitalized]
        cumulative_hospitalized = self.x_sol_final[11, :]  # TH
        cumulative_hospitalized = [int(round(x, 0)) for x in cumulative_hospitalized]
        total_detected_deaths = self.x_sol_final[14, :]  # DD
        total_detected_deaths = [int(round(x, 0)) for x in total_detected_deaths]
        active_ventilated = self.x_sol_final[12, :] + self.x_sol_final[13, :]  # DVR + DVD
        active_ventilated = [int(round(x, 0)) for x in active_ventilated]
        # Generation of the dataframe since today
        df_predictions_since_today_cont_country_prov = pd.DataFrame({
            "Continent": [self.continent for _ in range(n_days_since_today)],
            "Country": [self.country for _ in range(n_days_since_today)],
            "Province": [self.province for _ in range(n_days_since_today)],
            "Day": all_dates_since_today,
            "Total Detected": total_detected[n_days_btw_today_since_100:],
            "Active": active_cases[n_days_btw_today_since_100:],
            "Active Hospitalized": active_hospitalized[n_days_btw_today_since_100:],
            "Cumulative Hospitalized": cumulative_hospitalized[n_days_btw_today_since_100:],
            "Total Detected Deaths": total_detected_deaths[n_days_btw_today_since_100:],
            "Active Ventilated": active_ventilated[n_days_btw_today_since_100:],
        })

        # Generation of the dataframe from the day since 100th case
        all_dates_since_100 = [
            str((self.date_day_since100 + timedelta(days=i)).date())
            for i in range(self.x_sol_final.shape[1])
        ]
        df_predictions_since_100_cont_country_prov = pd.DataFrame({
            "Continent": [self.continent for _ in range(len(all_dates_since_100))],
            "Country": [self.country for _ in range(len(all_dates_since_100))],
            "Province": [self.province for _ in range(len(all_dates_since_100))],
            "Day": all_dates_since_100,
            "Total Detected": total_detected,
            "Active": active_cases,
            "Active Hospitalized": active_hospitalized,
            "Cumulative Hospitalized": cumulative_hospitalized,
            "Total Detected Deaths": total_detected_deaths,
            "Active Ventilated": active_ventilated,
        })
        return df_predictions_since_today_cont_country_prov, df_predictions_since_100_cont_country_prov

    def create_datasets_raw(self) -> (pd.DataFrame, pd.DataFrame):
        n_days_btw_today_since_100 = (datetime.now() - self.date_day_since100).days
        n_days_since_today = self.x_sol_final.shape[1] - n_days_btw_today_since_100
        all_dates_since_today = [
            str((datetime.now() + timedelta(days=i)).date())
            for i in range(n_days_since_today)
        ]

        df_predictions_since_today_cont_country_prov = pd.DataFrame({
            "Continent": [self.continent for _ in range(n_days_since_today)],
            "Country": [self.country for _ in range(n_days_since_today)],
            "Province": [self.province for _ in range(n_days_since_today)],
            "Day": all_dates_since_today
        })

        intr_since_today = pd.DataFrame(self.x_sol_final[:, n_days_btw_today_since_100:].transpose())

        intr_since_today.columns = ['S', 'E',  'I', 'AR', 'DHR', 'DQR', 'AD',
                'DHD', 'DQD', 'R', 'D', 'TH', 'DVR', 'DVD', 'DD', 'DT']

        df_predictions_since_today_cont_country_prov = pd.concat([df_predictions_since_today_cont_country_prov, intr_since_today], axis=1)

        # Generation of the dataframe from the day since 100th case
        all_dates_since_100 = [
            str((self.date_day_since100 + timedelta(days=i)).date())
            for i in range(self.x_sol_final.shape[1])
        ]
        df_predictions_since_100_cont_country_prov = pd.DataFrame({
            "Continent": [self.continent for _ in range(len(all_dates_since_100))],
            "Country": [self.country for _ in range(len(all_dates_since_100))],
            "Province": [self.province for _ in range(len(all_dates_since_100))],
            "Day": all_dates_since_100})

        intr_since_100 = pd.DataFrame(self.x_sol_final.transpose())

        intr_since_100.columns = ['S', 'E',  'I', 'AR', 'DHR', 'DQR', 'AD',
                'DHD', 'DQD', 'R', 'D', 'TH', 'DVR', 'DVD', 'DD', 'DT']

        df_predictions_since_100_cont_country_prov = pd.concat([df_predictions_since_100_cont_country_prov, intr_since_100], axis=1)

        return df_predictions_since_today_cont_country_prov, df_predictions_since_100_cont_country_prov

    def create_datasets_with_confidence_intervals(self, fitcasesnd, fitcasesd, past_prediction_file = "I://covid19orc//danger_map//predicted//Global_V2_20200720.csv", past_prediction_date = "2020-07-04", q = 0.5) -> (pd.DataFrame, pd.DataFrame):
        n_days_btw_today_since_100 = (datetime.now() - self.date_day_since100).days
        n_days_since_today = self.x_sol_final.shape[1] - n_days_btw_today_since_100
        all_dates_since_today = [
            str((datetime.now() + timedelta(days=i)).date())
            for i in range(n_days_since_today)
        ]
        # Predictions
        total_detected = self.x_sol_final[15, :]  # DT
        total_detected = [int(round(x, 0)) for x in total_detected]
        active_cases = (
                self.x_sol_final[4, :] + self.x_sol_final[5, :] + self.x_sol_final[7, :] + self.x_sol_final[8, :]
        )  # DHR + DQR + DHD + DQD
        active_cases = [int(round(x, 0)) for x in active_cases]
        active_hospitalized = self.x_sol_final[4, :] + self.x_sol_final[7, :]  # DHR + DHD
        active_hospitalized = [int(round(x, 0)) for x in active_hospitalized]
        cumulative_hospitalized = self.x_sol_final[11, :]  # TH
        cumulative_hospitalized = [int(round(x, 0)) for x in cumulative_hospitalized]
        total_detected_deaths = self.x_sol_final[14, :]  # DD
        total_detected_deaths = [int(round(x, 0)) for x in total_detected_deaths]
        active_ventilated = self.x_sol_final[12, :] + self.x_sol_final[13, :]  # DVR + DVD
        active_ventilated = [int(round(x, 0)) for x in active_ventilated]
        
        past_predictions = pd.read_csv(past_prediction_file)
        past_predictions = (past_predictions[(past_predictions['Day'] > past_prediction_date) & (past_predictions['Country'] == self.country) & (past_predictions['Province'] == self.province)]).sort_values("Day")
        if len(past_predictions) > 0:
            known_dates_since_100 = [
                str((self.date_day_since100 + timedelta(days=i)).date())
                for i in range(len(fitcasesnd))
            ]
            fitcasesnd_past = [y for x, y in zip(known_dates_since_100,fitcasesnd) if x > past_prediction_date]
            fitcasesd_past = [y for x, y in zip(known_dates_since_100,fitcasesd) if x > past_prediction_date]
            total_detected_past = past_predictions["Total Detected"].values[:len(fitcasesnd_past)]
            total_detected_deaths_past = past_predictions["Total Detected Deaths"].values[:len(fitcasesd_past)]
            residual_cases_lb = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesnd_past,total_detected_past)])) * scipy.stats.norm.ppf(0.5 - q /2)
            residual_cases_ub = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesnd_past,total_detected_past)])) * scipy.stats.norm.ppf(0.5 + q /2)
            residual_deaths_lb = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesd_past,total_detected_deaths_past)])) * scipy.stats.norm.ppf(0.5 - q /2)
            residual_deaths_ub = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesd_past,total_detected_deaths_past)])) *  scipy.stats.norm.ppf(0.5 + q /2)
                   
            # Generation of the dataframe since today
            df_predictions_since_today_cont_country_prov = pd.DataFrame({
                "Continent": [self.continent for _ in range(n_days_since_today)],
                "Country": [self.country for _ in range(n_days_since_today)],
                "Province": [self.province for _ in range(n_days_since_today)],
                "Day": all_dates_since_today,
                "Total Detected": total_detected[n_days_btw_today_since_100:],
                "Active": active_cases[n_days_btw_today_since_100:],
                "Active Hospitalized": active_hospitalized[n_days_btw_today_since_100:],
                "Cumulative Hospitalized": cumulative_hospitalized[n_days_btw_today_since_100:],
                "Total Detected Deaths": total_detected_deaths[n_days_btw_today_since_100:],
                "Active Ventilated": active_ventilated[n_days_btw_today_since_100:],
                "Total Detected True": [np.nan for _ in range(n_days_since_today)],
                "Total Detected Deaths True": [np.nan for _ in range(n_days_since_today)],       
                "Total Detected LB": make_increasing([max(int(round(v + residual_cases_lb * np.sqrt(c),0)),0) for c, v in enumerate(total_detected[n_days_btw_today_since_100:])]),
#                "Active LB": [max(int(round(v + residual_cases_lb * np.sqrt(c) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_cases[n_days_btw_today_since_100:], total_detected[n_days_btw_today_since_100:]))],
#                "Active Hospitalized LB": [max(int(round(v + residual_cases_lb * np.sqrt(c) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_hospitalized[n_days_btw_today_since_100:], total_detected[n_days_btw_today_since_100:]))],
#                "Cumulative Hospitalized LB": make_increasing([max(int(round(v + residual_cases_lb * np.sqrt(c) * v / u,0)),0) for c, (v, u) in enumerate(zip(cumulative_hospitalized[n_days_btw_today_since_100:], total_detected[n_days_btw_today_since_100:]))]),
                "Total Detected Deaths LB": make_increasing([max(int(round(v + residual_deaths_lb * np.sqrt(c),0)),0) for c, v in enumerate(total_detected_deaths[n_days_btw_today_since_100:])]),
#                "Active Ventilated LB": [max(int(round(v + residual_cases_lb * np.sqrt(c) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_ventilated[n_days_btw_today_since_100:], total_detected[n_days_btw_today_since_100:]))],
                "Total Detected UB": [max(int(round(v + residual_cases_ub * np.sqrt(c),0)),0) for c, v in enumerate(total_detected[n_days_btw_today_since_100:])],
#                "Active UB": [max(int(round(v + residual_cases_ub * np.sqrt(c) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_cases[n_days_btw_today_since_100:], total_detected[n_days_btw_today_since_100:]))],
#                "Active Hospitalized UB": [max(int(round(v + residual_cases_ub * np.sqrt(c) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_hospitalized[n_days_btw_today_since_100:], total_detected[n_days_btw_today_since_100:]))],
#                "Cumulative Hospitalized UB": [max(int(round(v + residual_cases_ub * np.sqrt(c) * v / u,0)),0) for c, (v, u) in enumerate(zip(cumulative_hospitalized[n_days_btw_today_since_100:], total_detected[n_days_btw_today_since_100:]))],
                "Total Detected Deaths UB": [max(int(round(v + residual_deaths_ub * np.sqrt(c),0)),0) for c, v in enumerate(total_detected_deaths[n_days_btw_today_since_100:])],
#                "Active Ventilated UB": [max(int(round(v + residual_cases_ub * np.sqrt(c) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_ventilated[n_days_btw_today_since_100:], total_detected[n_days_btw_today_since_100:]))],
            })
                    
    
            # Generation of the dataframe from the day since 100th case
            all_dates_since_100 = [
                str((self.date_day_since100 + timedelta(days=i)).date())
                for i in range(self.x_sol_final.shape[1])
            ]
            df_predictions_since_100_cont_country_prov = pd.DataFrame({
                "Continent": [self.continent for _ in range(len(all_dates_since_100))],
                "Country": [self.country for _ in range(len(all_dates_since_100))],
                "Province": [self.province for _ in range(len(all_dates_since_100))],
                "Day": all_dates_since_100,
                "Total Detected": total_detected,
                "Active": active_cases,
                "Active Hospitalized": active_hospitalized,
                "Cumulative Hospitalized": cumulative_hospitalized,
                "Total Detected Deaths": total_detected_deaths,
                "Active Ventilated": active_ventilated,
                "Total Detected True": fitcasesnd + [np.nan for _ in range(len(all_dates_since_100) - len(fitcasesnd))],
                "Total Detected Deaths True": fitcasesd + [np.nan for _ in range(len(all_dates_since_100) - len(fitcasesd))],
                "Total Detected LB": make_increasing([max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected)]),
#                "Active LB": [max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_cases, total_detected))],
#                "Active Hospitalized LB": [max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_hospitalized, total_detected))],
#                "Cumulative Hospitalized LB": make_increasing([max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(cumulative_hospitalized, total_detected))]),
                "Total Detected Deaths LB": make_increasing([max(int(round(v + residual_deaths_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected_deaths)]),
#                "Active Ventilated LB": [max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_ventilated, total_detected))],
                "Total Detected UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected)],
#                "Active UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_cases, total_detected))],
#                "Active Hospitalized UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_hospitalized, total_detected))],
#                "Cumulative Hospitalized UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(cumulative_hospitalized, total_detected))],
                "Total Detected Deaths UB": [max(int(round(v + residual_deaths_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected_deaths)],
#                "Active Ventilated UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_ventilated, total_detected))],
            })
        else:
            df_predictions_since_today_cont_country_prov = pd.DataFrame({
                "Continent": [self.continent for _ in range(n_days_since_today)],
                "Country": [self.country for _ in range(n_days_since_today)],
                "Province": [self.province for _ in range(n_days_since_today)],
                "Day": all_dates_since_today,
                "Total Detected": total_detected[n_days_btw_today_since_100:],
                "Active": active_cases[n_days_btw_today_since_100:],
                "Active Hospitalized": active_hospitalized[n_days_btw_today_since_100:],
                "Cumulative Hospitalized": cumulative_hospitalized[n_days_btw_today_since_100:],
                "Total Detected Deaths": total_detected_deaths[n_days_btw_today_since_100:],
                "Active Ventilated": active_ventilated[n_days_btw_today_since_100:],
                "Total Detected True": [np.nan for _ in range(n_days_since_today)],
                "Total Detected Deaths True": [np.nan for _ in range(n_days_since_today)],       
                "Total Detected LB": [np.nan for _ in range(n_days_since_today)],  
#                "Active LB": [np.nan for _ in range(n_days_since_today)],
#                "Active Hospitalized LB": [np.nan for _ in range(n_days_since_today)],
#                "Cumulative Hospitalized LB": [np.nan for _ in range(n_days_since_today)],
                "Total Detected Deaths LB": [np.nan for _ in range(n_days_since_today)],  
#                "Active Ventilated LB": [np.nan for _ in range(n_days_since_today)],
                "Total Detected UB": [np.nan for _ in range(n_days_since_today)],  
#                "Active UB": [np.nan for _ in range(n_days_since_today)],
#                "Active Hospitalized UB": [np.nan for _ in range(n_days_since_today)],
#                "Cumulative Hospitalized UB": [np.nan for _ in range(n_days_since_today)],
                "Total Detected Deaths UB": [np.nan for _ in range(n_days_since_today)],  
#                "Active Ventilated UB": [np.nan for _ in range(n_days_since_today)]
            })    
            # Generation of the dataframe from the day since 100th case
            all_dates_since_100 = [
                str((self.date_day_since100 + timedelta(days=i)).date())
                for i in range(self.x_sol_final.shape[1])
            ]
            df_predictions_since_100_cont_country_prov = pd.DataFrame({
                "Continent": [self.continent for _ in range(len(all_dates_since_100))],
                "Country": [self.country for _ in range(len(all_dates_since_100))],
                "Province": [self.province for _ in range(len(all_dates_since_100))],
                "Day": all_dates_since_100,
                "Total Detected": total_detected,
                "Active": active_cases,
                "Active Hospitalized": active_hospitalized,
                "Cumulative Hospitalized": cumulative_hospitalized,
                "Total Detected Deaths": total_detected_deaths,
                "Active Ventilated": active_ventilated,
                "Total Detected True": fitcasesnd + [np.nan for _ in range(len(all_dates_since_100) - len(fitcasesnd))],
                "Total Detected Deaths True": fitcasesd + [np.nan for _ in range(len(all_dates_since_100) - len(fitcasesd))],
                "Total Detected LB": [np.nan for _ in range(len(all_dates_since_100))],  
#                "Active LB":  [np.nan for _ in range(len(all_dates_since_100))],
#                "Active Hospitalized LB":  [np.nan for _ in range(len(all_dates_since_100))],
#                "Cumulative Hospitalized LB":  [np.nan for _ in range(len(all_dates_since_100))],
                "Total Detected Deaths LB":  [np.nan for _ in range(len(all_dates_since_100))],  
#                "Active Ventilated LB":  [np.nan for _ in range(len(all_dates_since_100))],
                "Total Detected UB":  [np.nan for _ in range(len(all_dates_since_100))],  
#                "Active UB":  [np.nan for _ in range(len(all_dates_since_100))],
#                "Active Hospitalized UB":  [np.nan for _ in range(len(all_dates_since_100))],
#                "Cumulative Hospitalized UB":  [np.nan for _ in range(len(all_dates_since_100))],
                "Total Detected Deaths UB":  [np.nan for _ in range(len(all_dates_since_100))],  
#                "Active Ventilated UB": [np.nan for _ in range(len(all_dates_since_100))]
            })            
        return df_predictions_since_today_cont_country_prov, df_predictions_since_100_cont_country_prov

    def create_datasets_predictions_scenario(
            self, policy="Lockdown", time=0, totalcases=None,
    ) -> (pd.DataFrame, pd.DataFrame):
        n_days_btw_today_since_100 = (datetime.now() - self.date_day_since100).days
        n_days_since_today = self.x_sol_final.shape[1] - n_days_btw_today_since_100
        all_dates_since_today = [
            str((datetime.now() + timedelta(days=i)).date())
            for i in range(n_days_since_today)
        ]
        # Predictions
        total_detected = self.x_sol_final[15, :]  # DT
        total_detected = [int(round(x, 0)) for x in total_detected]
        active_cases = (
                self.x_sol_final[4, :] + self.x_sol_final[5, :] + self.x_sol_final[7, :] + self.x_sol_final[8, :]
        )  # DHR + DQR + DHD + DQD
        active_cases = [int(round(x, 0)) for x in active_cases]
        active_hospitalized = self.x_sol_final[4, :] + self.x_sol_final[7, :]  # DHR + DHD
        active_hospitalized = [int(round(x, 0)) for x in active_hospitalized]
        cumulative_hospitalized = self.x_sol_final[11, :]  # TH
        cumulative_hospitalized = [int(round(x, 0)) for x in cumulative_hospitalized]
        total_detected_deaths = self.x_sol_final[14, :]  # DD
        total_detected_deaths = [int(round(x, 0)) for x in total_detected_deaths]
        active_ventilated = self.x_sol_final[12, :] + self.x_sol_final[13, :]  # DVR + DVD
        active_ventilated = [int(round(x, 0)) for x in active_ventilated]
        # Generation of the dataframe since today
        df_predictions_since_today_cont_country_prov = pd.DataFrame({
            "Policy": [policy for _ in range(n_days_since_today)],
            "Time": [TIME_DICT[time] for _ in range(n_days_since_today)],
            "Continent": [self.continent for _ in range(n_days_since_today)],
            "Country": [self.country for _ in range(n_days_since_today)],
            "Province": [self.province for _ in range(n_days_since_today)],
            "Day": all_dates_since_today,
            "Total Detected": total_detected[n_days_btw_today_since_100:],
            "Active": active_cases[n_days_btw_today_since_100:],
            "Active Hospitalized": active_hospitalized[n_days_btw_today_since_100:],
            "Cumulative Hospitalized": cumulative_hospitalized[n_days_btw_today_since_100:],
            "Total Detected Deaths": total_detected_deaths[n_days_btw_today_since_100:],
            "Active Ventilated": active_ventilated[n_days_btw_today_since_100:],
        })

        # Generation of the dataframe from the day since 100th case
        all_dates_since_100 = [
            str((self.date_day_since100 + timedelta(days=i)).date())
            for i in range(self.x_sol_final.shape[1])
        ]
        df_predictions_since_100_cont_country_prov = pd.DataFrame({
            "Policy": [policy for _ in range(len(all_dates_since_100))],
            "Time": [TIME_DICT[time] for _ in range(len(all_dates_since_100))],
            "Continent": [self.continent for _ in range(len(all_dates_since_100))],
            "Country": [self.country for _ in range(len(all_dates_since_100))],
            "Province": [self.province for _ in range(len(all_dates_since_100))],
            "Day": all_dates_since_100,
            "Total Detected": total_detected,
            "Active": active_cases,
            "Active Hospitalized": active_hospitalized,
            "Cumulative Hospitalized": cumulative_hospitalized,
            "Total Detected Deaths": total_detected_deaths,
            "Active Ventilated": active_ventilated,
        })
        if totalcases is not None:  # Merging the historical values to both dataframes when available
            df_predictions_since_today_cont_country_prov = df_predictions_since_today_cont_country_prov.merge(
                totalcases[["country", "province", "date", "case_cnt", "death_cnt"]].fillna('None') ,
                left_on=["Country", "Province", "Day"],
                right_on=["country", "province", "date"],
                how="left",
            )
            df_predictions_since_today_cont_country_prov.rename(
                columns={"case_cnt": "Total Detected True", "death_cnt": "Total Detected Deaths True"},
                inplace=True,
            )
            df_predictions_since_today_cont_country_prov.drop(
                ["country", "province", "date"], axis=1, inplace=True
            )
            df_predictions_since_100_cont_country_prov = df_predictions_since_100_cont_country_prov.merge(
                totalcases[["country", "province", "date", "case_cnt", "death_cnt"]].fillna('None'),
                left_on=["Country", "Province", "Day"],
                right_on=["country", "province", "date"],
                how="left",
            )
            df_predictions_since_100_cont_country_prov.rename(
                columns={"case_cnt": "Total Detected True", "death_cnt": "Total Detected Deaths True"},
                inplace=True,
            )
            df_predictions_since_100_cont_country_prov.drop(
                ["country", "province", "date"], axis=1, inplace=True
            )
        return df_predictions_since_today_cont_country_prov, df_predictions_since_100_cont_country_prov


class DELPHIAggregations:
    @staticmethod
    def get_aggregation_per_country(df: pd.DataFrame) -> pd.DataFrame:
        df = df[df["Province"] != "None"]
        df_agg_country = df.groupby(["Continent", "Country", "Day"]).sum().reset_index()
        df_agg_country["Province"] = "None"
        df_agg_country = df_agg_country[df.columns]
        return df_agg_country

    @staticmethod
    def get_aggregation_per_continent(df: pd.DataFrame) -> pd.DataFrame:
        df_agg_continent = df.groupby(["Continent", "Day"]).sum().reset_index()
        df_agg_continent["Country"] = "None"
        df_agg_continent["Province"] = "None"
        df_agg_continent = df_agg_continent[df.columns]
        return df_agg_continent

    @staticmethod
    def get_aggregation_world(df: pd.DataFrame) -> pd.DataFrame:
        df_agg_world = df.groupby("Day").sum().reset_index()
        df_agg_world["Continent"] = "None"
        df_agg_world["Country"] = "None"
        df_agg_world["Province"] = "None"
        df_agg_world = df_agg_world[df.columns]
        return df_agg_world

    @staticmethod
    def get_aggregation_per_country_with_cf(df: pd.DataFrame, past_prediction_file = "I://covid19orc//danger_map//predicted//Global_V2_20200720.csv", past_prediction_date = "2020-07-04", q = 0.5) -> pd.DataFrame:
        df = df[df["Province"] != "None"]
        columns_without_bounds = [x for x in df.columns if ("LB" not in x) and ("UB" not in x)]
        df_agg_country = df[columns_without_bounds].groupby(["Continent", "Country", "Day"]).sum(min_count = 1).reset_index()
        df_agg_country["Province"] = "None"
        df_agg_country = df_agg_country[columns_without_bounds]
        aggregated_countries = set(zip(df_agg_country["Country"],df_agg_country["Province"]))
        past_predictions = pd.read_csv(past_prediction_file)
        list_df_aggregated_countries = []
        for country, province in aggregated_countries:
            past_predictions_temp = (past_predictions[(past_predictions['Day'] > past_prediction_date) & (past_predictions['Country'] == country) & (past_predictions['Province'] == province)]).sort_values("Day")
            df_agg_country_temp = (df_agg_country[(df_agg_country['Country'] == country) & (df_agg_country['Province'] == province)]).sort_values("Day").reset_index(drop=True)
            total_detected = df_agg_country_temp['Total Detected']
            total_detected_deaths = df_agg_country_temp['Total Detected Deaths']
            active_cases = df_agg_country_temp['Active']
            active_hospitalized = df_agg_country_temp['Active Hospitalized']
            cumulative_hospitalized = df_agg_country_temp['Cumulative Hospitalized']
            active_ventilated = df_agg_country_temp['Active Ventilated']
            fitcasesnd = df_agg_country_temp['Total Detected True']
            fitcasesd = df_agg_country_temp['Total Detected Deaths True']
            since_100_dates = df_agg_country_temp['Day']
            n_days_btw_today_since_100 = (datetime.now() - pd.to_datetime(min(since_100_dates))).days
            if len(past_predictions_temp) > 0:
                fitcasesnd_past = [y for x, y in zip(since_100_dates,fitcasesnd) if ((x > past_prediction_date) and (not np.isnan(y)))]
                fitcasesd_past = [y for x, y in zip(since_100_dates,fitcasesd) if ((x > past_prediction_date) and (not np.isnan(y)))]
                total_detected_past = past_predictions_temp["Total Detected"].values[:len(fitcasesnd_past)]
                total_detected_deaths_past = past_predictions_temp["Total Detected Deaths"].values[:len(fitcasesd_past)]
                residual_cases_lb = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesnd_past,total_detected_past)])) * scipy.stats.norm.ppf(0.5 - q /2)
                residual_cases_ub = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesnd_past,total_detected_past)])) * scipy.stats.norm.ppf(0.5 + q /2)
                residual_deaths_lb = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesd_past,total_detected_deaths_past)])) * scipy.stats.norm.ppf(0.5 - q /2)
                residual_deaths_ub = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesd_past,total_detected_deaths_past)])) *  scipy.stats.norm.ppf(0.5 + q /2)

                # Generation of the dataframe from the day since 100th case
                df_predictions_since_100_cont_country_prov = pd.DataFrame({
                    "Total Detected LB": make_increasing([max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected)]),
#                    "Active LB": [max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_cases, total_detected))],
#                    "Active Hospitalized LB": [max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_hospitalized, total_detected))],
#                    "Cumulative Hospitalized LB": make_increasing([max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(cumulative_hospitalized, total_detected))]),
                    "Total Detected Deaths LB": make_increasing([max(int(round(v + residual_deaths_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected_deaths)]),
#                    "Active Ventilated LB": [max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_ventilated, total_detected))],
                    "Total Detected UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected)],
#                    "Active UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_cases, total_detected))],
#                    "Active Hospitalized UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_hospitalized, total_detected))],
#                    "Cumulative Hospitalized UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(cumulative_hospitalized, total_detected))],
                    "Total Detected Deaths UB": [max(int(round(v + residual_deaths_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected_deaths)],
#                    "Active Ventilated UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_ventilated, total_detected))],
                })
                df_agg_country_temp = pd.concat([df_agg_country_temp, df_predictions_since_100_cont_country_prov], axis = 1)
            else:
                df_predictions_since_100_cont_country_prov = pd.DataFrame({
                    "Total Detected LB": [np.nan for _ in range(len(df_agg_country_temp))],
#                    "Active LB":  [np.nan for _ in range(len(df_agg_country_temp))],
#                    "Active Hospitalized LB":  [np.nan for _ in range(len(df_agg_country_temp))],
#                    "Cumulative Hospitalized LB":  [np.nan for _ in range(len(df_agg_country_temp))],
                    "Total Detected Deaths LB":  [np.nan for _ in range(len(df_agg_country_temp))],
#                    "Active Ventilated LB":  [np.nan for _ in range(len(df_agg_country_temp))],
                    "Total Detected UB":  [np.nan for _ in range(len(df_agg_country_temp))],
#                    "Active UB":  [np.nan for _ in range(len(df_agg_country_temp))],
#                    "Active Hospitalized UB":  [np.nan for _ in range(len(df_agg_country_temp))],
#                    "Cumulative Hospitalized UB":  [np.nan for _ in range(len(df_agg_country_temp))],
                    "Total Detected Deaths UB":  [np.nan for _ in range(len(df_agg_country_temp))],
#                    "Active Ventilated UB": [np.nan for _ in range(len(df_agg_country_temp))]
                })
                df_agg_country_temp = pd.concat([df_agg_country_temp, df_predictions_since_100_cont_country_prov], axis = 1)

            list_df_aggregated_countries.append(df_agg_country_temp)
        df_agg_country_final = pd.concat(list_df_aggregated_countries)
        return df_agg_country_final

    @staticmethod
    def get_aggregation_per_continent_with_cf(df: pd.DataFrame, past_prediction_file = "I://covid19orc//danger_map//predicted//Global_V2_20200720.csv", past_prediction_date = "2020-07-04", q = 0.5) -> pd.DataFrame:
        columns_without_bounds = [x for x in df.columns if ("LB" not in x) and ("UB" not in x)]
        df_agg_continent = df[columns_without_bounds].groupby(["Continent", "Day"]).sum(min_count = 1).reset_index()
        df_agg_continent["Country"] = "None"
        df_agg_continent["Province"] = "None"
        df_agg_continent = df_agg_continent[columns_without_bounds]
        aggregated_continents = set(zip(df_agg_continent["Continent"], df_agg_continent["Country"],df_agg_continent["Province"]))
        past_predictions = pd.read_csv(past_prediction_file)
        list_df_aggregated_continents = []
        for continent, country, province in aggregated_continents:
            past_predictions_temp = (past_predictions[(past_predictions['Day'] > past_prediction_date) & (past_predictions['Continent'] == continent) & (past_predictions['Country'] == country) & (past_predictions['Country'] == province)]).sort_values("Day")
            df_agg_continent_temp = (df_agg_continent[(df_agg_continent['Continent'] == continent)]).sort_values("Day").reset_index(drop=True)
            total_detected = df_agg_continent_temp['Total Detected']
            total_detected_deaths = df_agg_continent_temp['Total Detected Deaths']
            active_cases = df_agg_continent_temp['Active']
            active_hospitalized = df_agg_continent_temp['Active Hospitalized']
            cumulative_hospitalized = df_agg_continent_temp['Cumulative Hospitalized']
            active_ventilated = df_agg_continent_temp['Active Ventilated']
            fitcasesnd = df_agg_continent_temp['Total Detected True']
            fitcasesd = df_agg_continent_temp['Total Detected Deaths True']
            since_100_dates = df_agg_continent_temp['Day']
            n_days_btw_today_since_100 = (datetime.now() - pd.to_datetime(min(since_100_dates))).days
            if len(past_predictions_temp) > 0:
                fitcasesnd_past = [y for x, y in zip(since_100_dates,fitcasesnd) if ((x > past_prediction_date) and (not np.isnan(y)))]
                fitcasesd_past = [y for x, y in zip(since_100_dates,fitcasesd) if ((x > past_prediction_date) and (not np.isnan(y)))]
                total_detected_past = past_predictions_temp["Total Detected"].values[:len(fitcasesnd_past)]
                total_detected_deaths_past = past_predictions_temp["Total Detected Deaths"].values[:len(fitcasesd_past)]
                residual_cases_lb = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesnd_past,total_detected_past)])) * scipy.stats.norm.ppf(0.5 - q /2)
                residual_cases_ub = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesnd_past,total_detected_past)])) * scipy.stats.norm.ppf(0.5 + q /2)
                residual_deaths_lb = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesd_past,total_detected_deaths_past)])) * scipy.stats.norm.ppf(0.5 - q /2)
                residual_deaths_ub = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesd_past,total_detected_deaths_past)])) *  scipy.stats.norm.ppf(0.5 + q /2)
                # Generation of the dataframe from the day since 100th case
                df_predictions_since_100_cont_country_prov = pd.DataFrame({
                    "Total Detected LB": make_increasing([max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected)]),
#                    "Active LB": [max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_cases, total_detected))],
#                    "Active Hospitalized LB": [max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_hospitalized, total_detected))],
#                    "Cumulative Hospitalized LB": make_increasing([max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(cumulative_hospitalized, total_detected))]),
                    "Total Detected Deaths LB": make_increasing([max(int(round(v + residual_deaths_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected_deaths)]),
#                    "Active Ventilated LB": [max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_ventilated, total_detected))],
                    "Total Detected UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected)],
#                    "Active UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_cases, total_detected))],
#                    "Active Hospitalized UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_hospitalized, total_detected))],
#                    "Cumulative Hospitalized UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(cumulative_hospitalized, total_detected))],
                    "Total Detected Deaths UB": [max(int(round(v + residual_deaths_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected_deaths)],
#                    "Active Ventilated UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_ventilated, total_detected))],
                })
                df_agg_continent_temp = pd.concat([df_agg_continent_temp, df_predictions_since_100_cont_country_prov], axis = 1)
            else:
                df_predictions_since_100_cont_country_prov = pd.DataFrame({
                    "Total Detected LB": [np.nan for _ in range(len(df_agg_continent_temp))],
#                    "Active LB":  [np.nan for _ in range(len(df_agg_continent_temp))],
#                    "Active Hospitalized LB":  [np.nan for _ in range(len(df_agg_continent_temp))],
#                    "Cumulative Hospitalized LB":  [np.nan for _ in range(len(df_agg_continent_temp))],
                    "Total Detected Deaths LB":  [np.nan for _ in range(len(df_agg_continent_temp))],
#                    "Active Ventilated LB":  [np.nan for _ in range(len(df_agg_continent_temp))],
                    "Total Detected UB":  [np.nan for _ in range(len(df_agg_continent_temp))],
#                    "Active UB":  [np.nan for _ in range(len(df_agg_continent_temp))],
#                    "Active Hospitalized UB":  [np.nan for _ in range(len(df_agg_continent_temp))],
#                    "Cumulative Hospitalized UB":  [np.nan for _ in range(len(df_agg_continent_temp))],
                    "Total Detected Deaths UB":  [np.nan for _ in range(len(df_agg_continent_temp))],
#                    "Active Ventilated UB": [np.nan for _ in range(len(df_agg_continent_temp))]
                })
                df_agg_continent_temp = pd.concat([df_agg_continent_temp, df_predictions_since_100_cont_country_prov], axis = 1)

            list_df_aggregated_continents.append(df_agg_continent_temp)
        df_agg_continent_final = pd.concat(list_df_aggregated_continents)
        return df_agg_continent_final

    @staticmethod
    def get_aggregation_world_with_cf(df: pd.DataFrame, past_prediction_file = "I://covid19orc//danger_map//predicted//Global_V2_20200720.csv", past_prediction_date = "2020-07-04", q = 0.5) -> pd.DataFrame:
        columns_without_bounds = [x for x in df.columns if ("LB" not in x) and ("UB" not in x)]
        df_agg_world = df[columns_without_bounds].groupby(["Day"]).sum(min_count = 1).reset_index()
        df_agg_world["Continent"] = "None"
        df_agg_world["Country"] = "None"
        df_agg_world["Province"] = "None"
        df_agg_world = df_agg_world[columns_without_bounds]
        past_predictions = pd.read_csv(past_prediction_file)
        past_predictions_temp = (past_predictions[(past_predictions['Day'] > past_prediction_date) & (past_predictions['Continent'] == "None") & (past_predictions['Country'] == "None") & (past_predictions['Province'] == "None")]).sort_values("Day")
        total_detected = df_agg_world['Total Detected']
        total_detected_deaths = df_agg_world['Total Detected Deaths']
        active_cases = df_agg_world['Active']
        active_hospitalized = df_agg_world['Active Hospitalized']
        cumulative_hospitalized = df_agg_world['Cumulative Hospitalized']
        active_ventilated = df_agg_world['Active Ventilated']
        fitcasesnd = df_agg_world['Total Detected True']
        fitcasesd = df_agg_world['Total Detected Deaths True']
        since_100_dates = df_agg_world['Day']
        n_days_btw_today_since_100 = (datetime.now() - pd.to_datetime(min(since_100_dates))).days
        if len(past_predictions_temp) > 0:
            fitcasesnd_past = [y for x, y in zip(since_100_dates,fitcasesnd) if ((x > past_prediction_date) and (not np.isnan(y)))]
            fitcasesd_past = [y for x, y in zip(since_100_dates,fitcasesd) if ((x > past_prediction_date) and (not np.isnan(y)))]
            total_detected_past = past_predictions_temp["Total Detected"].values[:len(fitcasesnd_past)]
            total_detected_deaths_past = past_predictions_temp["Total Detected Deaths"].values[:len(fitcasesd_past)]
            residual_cases_lb = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesnd_past,total_detected_past)])) * scipy.stats.norm.ppf(0.5 - q /2)
            residual_cases_ub = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesnd_past,total_detected_past)])) * scipy.stats.norm.ppf(0.5 + q /2)
            residual_deaths_lb = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesd_past,total_detected_deaths_past)])) * scipy.stats.norm.ppf(0.5 - q /2)
            residual_deaths_ub = np.sqrt(np.mean([(x- y) ** 2 for x,y in zip(fitcasesd_past,total_detected_deaths_past)])) *  scipy.stats.norm.ppf(0.5 + q /2)

            # Generation of the dataframe from the day since 100th case
            df_predictions_since_100_cont_country_prov = pd.DataFrame({
                "Total Detected LB": make_increasing([max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected)]),
#                "Active LB": [max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_cases, total_detected))],
#                "Active Hospitalized LB": [max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_hospitalized, total_detected))],
#                "Cumulative Hospitalized LB": make_increasing([max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(cumulative_hospitalized, total_detected))]),
                "Total Detected Deaths LB": make_increasing([max(int(round(v + residual_deaths_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected_deaths)]),
#                "Active Ventilated LB": [max(int(round(v + residual_cases_lb * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_ventilated, total_detected))],
                "Total Detected UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected)],
#                "Active UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_cases, total_detected))],
#                "Active Hospitalized UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_hospitalized, total_detected))],
#                "Cumulative Hospitalized UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(cumulative_hospitalized, total_detected))],
                "Total Detected Deaths UB": [max(int(round(v + residual_deaths_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)),0)),0) for c, v in enumerate(total_detected_deaths)],
#                "Active Ventilated UB": [max(int(round(v + residual_cases_ub * np.sqrt(max(c - n_days_btw_today_since_100, 0)) * v / u,0)),0) for c, (v, u) in enumerate(zip(active_ventilated, total_detected))],
            })
            df_agg_world_final = pd.concat([df_agg_world, df_predictions_since_100_cont_country_prov], axis = 1)
        else:
            df_predictions_since_100_cont_country_prov = pd.DataFrame({
                "Total Detected LB": [np.nan for _ in range(len(df_agg_world))],
#                "Active LB":  [np.nan for _ in range(len(df_agg_world))],
#                "Active Hospitalized LB":  [np.nan for _ in range(len(df_agg_world))],
#                "Cumulative Hospitalized LB":  [np.nan for _ in range(len(df_agg_world))],
                "Total Detected Deaths LB":  [np.nan for _ in range(len(df_agg_world))],
#                "Active Ventilated LB":  [np.nan for _ in range(len(df_agg_world))],
                "Total Detected UB":  [np.nan for _ in range(len(df_agg_world))],
#                "Active UB":  [np.nan for _ in range(len(df_agg_world))],
#                "Active Hospitalized UB":  [np.nan for _ in range(len(df_agg_world))],
#                "Cumulative Hospitalized UB":  [np.nan for _ in range(len(df_agg_world))],
                "Total Detected Deaths UB":  [np.nan for _ in range(len(df_agg_world))],
#                "Active Ventilated UB": [np.nan for _ in range(len(df_agg_world))]
            })
            df_agg_world_final = pd.concat([df_agg_world, df_predictions_since_100_cont_country_prov], axis = 1)
        return df_agg_world_final

    @staticmethod
    def append_all_aggregations(df: pd.DataFrame) -> pd.DataFrame:
        df_agg_since_today_per_country = DELPHIAggregations.get_aggregation_per_country(df)
        df_agg_since_today_per_continent = DELPHIAggregations.get_aggregation_per_continent(df)
        df_agg_since_today_world = DELPHIAggregations.get_aggregation_world(df)
        df = pd.concat([
            df, df_agg_since_today_per_country,
            df_agg_since_today_per_continent, df_agg_since_today_world
        ])
        df.sort_values(["Continent", "Country", "Province", "Day"], inplace=True)
        return df

    def append_all_aggregations_cf(df: pd.DataFrame, past_prediction_file = "I://covid19orc//danger_map//predicted//Global_V2_20200720.csv", past_prediction_date = "2020-07-04", q = 0.5) -> pd.DataFrame:
        df_agg_since_today_per_country = DELPHIAggregations.get_aggregation_per_country_with_cf(df, past_prediction_file = past_prediction_file, past_prediction_date = past_prediction_date, q = q)
        df_agg_since_today_per_continent = DELPHIAggregations.get_aggregation_per_continent_with_cf(df, past_prediction_file = past_prediction_file, past_prediction_date = past_prediction_date, q = q)
        df_agg_since_today_world = DELPHIAggregations.get_aggregation_world_with_cf(df, past_prediction_file = past_prediction_file, past_prediction_date = past_prediction_date, q = q)
        df = pd.concat([
            df, df_agg_since_today_per_country,
            df_agg_since_today_per_continent, df_agg_since_today_world
        ])
        df.sort_values(["Continent", "Country", "Province", "Day"], inplace=True)
        return df

class DELPHIAggregationsPolicies:
    @staticmethod
    def get_aggregation_per_country(df: pd.DataFrame) -> pd.DataFrame:
        df = df[df["Province"] != "None"]
        df_agg_country = df.groupby(["Policy", "Time", "Continent", "Country", "Day"]).sum().reset_index()
        df_agg_country["Province"] = "None"
        df_agg_country = df_agg_country[[
        'Policy', 'Time', 'Continent', 'Country', 'Province', 'Day', 'Total Detected', 'Active',
            'Active Hospitalized', 'Cumulative Hospitalized', 'Total Detected Deaths', 'Active Ventilated'
        ]]
        return df_agg_country

    @staticmethod
    def get_aggregation_per_continent(df: pd.DataFrame) -> pd.DataFrame:
        df_agg_continent = df.groupby(["Policy", "Time", "Continent", "Day"]).sum().reset_index()
        df_agg_continent["Country"] = "None"
        df_agg_continent["Province"] = "None"
        df_agg_continent = df_agg_continent[[
            'Policy', 'Time', 'Continent', 'Country', 'Province', 'Day', 'Total Detected', 'Active',
            'Active Hospitalized', 'Cumulative Hospitalized', 'Total Detected Deaths', 'Active Ventilated'
        ]]
        return df_agg_continent

    @staticmethod
    def get_aggregation_world(df: pd.DataFrame) -> pd.DataFrame:
        df_agg_world = df.groupby(["Policy", "Time", "Day"]).sum().reset_index()
        df_agg_world["Continent"] = "None"
        df_agg_world["Country"] = "None"
        df_agg_world["Province"] = "None"
        df_agg_world = df_agg_world[[
            'Policy', 'Time', 'Continent', 'Country', 'Province', 'Day', 'Total Detected', 'Active',
            'Active Hospitalized', 'Cumulative Hospitalized', 'Total Detected Deaths', 'Active Ventilated'
        ]]
        return df_agg_world

    @staticmethod
    def append_all_aggregations(df: pd.DataFrame) -> pd.DataFrame:
        df_agg_since_today_per_country = DELPHIAggregations.get_aggregation_per_country(df)
        df_agg_since_today_per_continent = DELPHIAggregations.get_aggregation_per_continent(df)
        df_agg_since_today_world = DELPHIAggregations.get_aggregation_world(df)
        df = pd.concat([
            df, df_agg_since_today_per_country,
            df_agg_since_today_per_continent, df_agg_since_today_world
        ])
        df.sort_values(["Policy", "Time", "Continent", "Country", "Province", "Day"], inplace=True)
        return df


def get_initial_conditions(params_fitted, global_params_fixed):
    alpha, days, r_s, r_dth, p_dth, r_dthdecay, k1, k2 = params_fitted[:8]
    N, PopulationCI, PopulationR, PopulationD, PopulationI, p_d, p_h, p_v = global_params_fixed
    S_0 = (
            (N - PopulationCI / p_d) -
            (PopulationCI / p_d * (k1 + k2)) -
            (PopulationR / p_d) -
            (PopulationD / p_d)
    )
    E_0 = PopulationCI / p_d * k1
    I_0 = PopulationCI / p_d * k2
    AR_0 = (PopulationCI / p_d - PopulationCI) * (1 - p_dth)
    DHR_0 = (PopulationCI * p_h) * (1 - p_dth)
    DQR_0 = PopulationCI * (1 - p_h) * (1 - p_dth)
    AD_0 = (PopulationCI / p_d - PopulationCI) * p_dth
    DHD_0 = PopulationCI * p_h * p_dth
    DQD_0 = PopulationCI * (1 - p_h) * p_dth
    R_0 = PopulationR / p_d
    D_0 = PopulationD / p_d
    TH_0 = PopulationCI * p_h
    DVR_0 = (PopulationCI * p_h * p_v) * (1 - p_dth)
    DVD_0 = (PopulationCI * p_h * p_v) * p_dth
    DD_0 = PopulationD
    DT_0 = PopulationI
    x_0_cases = [
        S_0, E_0, I_0, AR_0, DHR_0, DQR_0, AD_0, DHD_0, DQD_0,
        R_0, D_0, TH_0, DVR_0, DVD_0, DD_0, DT_0
    ]
    return x_0_cases

def get_initial_conditions_with_testing(params_fitted, global_params_fixed):
    alpha, days, r_s, r_dth, p_dth, k1, k2, beta_0, beta_1 = params_fitted
    N, PopulationCI, PopulationR, PopulationD, PopulationI, p_d, p_h, p_v = global_params_fixed
    S_0 = (
            (N - PopulationCI / p_d) -
            (PopulationCI / p_d * (k1 + k2)) -
            (PopulationR / p_d) -
            (PopulationD / p_d)
    )
    E_0 = PopulationCI / p_d * k1
    I_0 = PopulationCI / p_d * k2
    AR_0 = (PopulationCI / p_d - PopulationCI) * (1 - p_dth)
    DHR_0 = (PopulationCI * p_h) * (1 - p_dth)
    DQR_0 = PopulationCI * (1 - p_h) * (1 - p_dth)
    AD_0 = (PopulationCI / p_d - PopulationCI) * p_dth
    DHD_0 = PopulationCI * p_h * p_dth
    DQD_0 = PopulationCI * (1 - p_h) * p_dth
    R_0 = PopulationR / p_d
    D_0 = PopulationD / p_d
    TH_0 = PopulationCI * p_h
    DVR_0 = (PopulationCI * p_h * p_v) * (1 - p_dth)
    DVD_0 = (PopulationCI * p_h * p_v) * p_dth
    DD_0 = PopulationD
    DT_0 = PopulationI
    x_0_cases = [
        S_0, E_0, I_0, AR_0, DHR_0, DQR_0, AD_0, DHD_0, DQD_0,
        R_0, D_0, TH_0, DVR_0, DVD_0, DD_0, DT_0
    ]
    return x_0_cases


def create_fitting_data_from_validcases(validcases):
    validcases_nondeath = validcases["case_cnt"].tolist()
    validcases_death = validcases["death_cnt"].tolist()
    balance = validcases_nondeath[-1] / max(validcases_death[-1], 10) / 3
    fitcasesnd = validcases_nondeath
    fitcasesd = validcases_death
    return balance, fitcasesnd, fitcasesd


def sign_mape(y_true, y_pred):
    # Mean Percentage Error, without the absolute value
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    mpe = np.mean((y_true - y_pred)[y_true > 0] / y_true[y_true > 0]) * 100
    sign = np.sign(mpe)
    return sign


def mape_daily_delta_since_last_train(true_last_train, pred_last_train, y_true, y_pred):
    delta_true = np.array([y_true_i - true_last_train for y_true_i in y_true])
    delta_pred = np.array([y_pred_i - pred_last_train for y_pred_i in y_pred])
    mape_daily_delta = np.mean(
        np.abs(delta_true - delta_pred)[delta_true > 0]/delta_true[delta_true > 0]
    ) * 100
    return mape_daily_delta


def mse(y_true, y_pred):
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    mse = np.mean((y_true - y_pred)**2)
    return mse


def mae_and_mape(y_true, y_pred):
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    mae = np.mean(np.abs((y_true - y_pred)))
    mape = np.mean(np.abs((y_true - y_pred)[y_true > 0] / y_true[y_true > 0])) * 100
    return mae, mape


def mape(y_true, y_pred):
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    mape = np.mean(np.abs((y_true - y_pred)[y_true > 0] / y_true[y_true > 0])) * 100
    return mape


def convert_dates_us_policies(x):
    if x == "Not implemented":
        return np.nan
    else:
        x_long = x + "20"
        return pd.to_datetime(x_long, format="%d-%b-%Y")


def check_us_policy_data_consistency(policies: list, df_policy_raw_us: pd.DataFrame):
    for policy in policies:
        assert (len(df_policy_raw_us.loc[
                    (df_policy_raw_us[f"{policy}_start_date"].isnull()) &
                    (~df_policy_raw_us[f"{policy}_end_date"].isnull()), :
        ]) == 0), f"Problem in data, policy {policy} has no start date but has an end date"


def create_features_from_ihme_dates(
        df_policy_raw_us: pd.DataFrame,
        dict_state_to_policy_dates: dict,
        policies: list,
) -> pd.DataFrame:
    list_df_concat = []
    n_dates = (datetime.now() - datetime(2020, 3, 1)).days + 1
    date_range = [
        datetime(2020, 3, 1) + timedelta(days=i)
        for i in range(n_dates)
    ]
    for location in df_policy_raw_us.location_name.unique():
        df_temp = pd.DataFrame({
            "continent": ["North America" for _ in range(len(date_range))],
            "country": ["US" for _ in range(len(date_range))],
            "province": [location for _ in range(len(date_range))],
            "date": date_range,
        })
        for policy in policies:
            start_date_policy_location = dict_state_to_policy_dates[location][policy][0]
            start_date_policy_location = (
                start_date_policy_location if start_date_policy_location is not np.nan
                else "2030-01-02"
            )
            end_date_policy_location = (dict_state_to_policy_dates[location][policy][1])
            end_date_policy_location = (
                end_date_policy_location if end_date_policy_location is not np.nan
                else "2030-01-01"
            )
            df_temp[policy] = 0
            df_temp.loc[
                ((df_temp.date >= start_date_policy_location) &
                 (df_temp.date <= end_date_policy_location)),
                policy
            ] = 1

        list_df_concat.append(df_temp)

    df_policies_US = pd.concat(list_df_concat).reset_index(drop=True)
    df_policies_US.rename(columns={
        "travel_limit": "Travel_severely_limited",
        "stay_home": "Stay_at_home_order",
        "educational_fac": "Educational_Facilities_Closed",
        "any_gathering_restrict": "Mass_Gathering_Restrictions",
        "any_business": "Initial_Business_Closure",
        "all_non-ess_business": "Non_Essential_Services_Closed"
    }, inplace=True)
    return df_policies_US


def create_final_policy_features_us(df_policies_US: pd.DataFrame) -> pd.DataFrame:
    df_policies_US_final = deepcopy(df_policies_US)
    msr = future_policies
    df_policies_US_final[msr[0]] = (df_policies_US.sum(axis=1) == 0).apply(lambda x: int(x))
    df_policies_US_final[msr[1]] = [int(a and b) for a, b in
                                                        zip(df_policies_US.sum(axis=1) == 1,
                                                            df_policies_US['Mass_Gathering_Restrictions'] == 1)]
    df_policies_US_final[msr[2]] = [
        int(a and b and c) for a, b, c in zip(
            df_policies_US.sum(axis=1) > 0,
            df_policies_US['Mass_Gathering_Restrictions'] == 0,
            df_policies_US['Stay_at_home_order'] == 0,
        )
    ]
    df_policies_US_final[msr[3]] = [
        int(a and b and c)
        for a, b, c in zip(
            df_policies_US.sum(axis=1) == 2,
            df_policies_US['Educational_Facilities_Closed'] == 1,
            df_policies_US['Mass_Gathering_Restrictions'] == 1,
        )
    ]
    df_policies_US_final[msr[4]] = [
        int(a and b and c and d) for a, b, c, d in zip(
            df_policies_US.sum(axis=1) > 1,
            df_policies_US['Educational_Facilities_Closed'] == 0,
            df_policies_US['Mass_Gathering_Restrictions'] == 1,
            df_policies_US['Stay_at_home_order'] == 0,
        )
    ]
    df_policies_US_final[msr[5]] = [
        int(a and b and c and d) for a, b, c, d in zip(
            df_policies_US.sum(axis=1) > 2,
            df_policies_US['Educational_Facilities_Closed'] == 1,
            df_policies_US['Mass_Gathering_Restrictions'] == 1,
            df_policies_US['Stay_at_home_order'] == 0,
        )
    ]
    df_policies_US_final[msr[6]] = (df_policies_US['Stay_at_home_order'] == 1).apply(lambda x: int(x))
    df_policies_US_final['country'] = "US"
    df_policies_US_final = df_policies_US_final.loc[:, ['country', 'province', 'date'] + msr]
    return df_policies_US_final


def read_policy_data_us_only(filepath_data_sandbox: str):
    policies = [
        "travel_limit", "stay_home", "educational_fac", "any_gathering_restrict",
        "any_business", "all_non-ess_business"
    ]
    list_US_states = [
        'Alabama', 'Alaska', 'Arizona', 'Arkansas',
        'California', 'Colorado', 'Connecticut', 'Delaware',
        'District of Columbia', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
        'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
        'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
        'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
        'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
        'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon',
        'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
        'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
        'West Virginia', 'Wisconsin', 'Wyoming'
    ]
    df = pd.read_csv(filepath_data_sandbox + "12062020_raw_policy_data_us_only.csv")
    df = df[df.location_name.isin(list_US_states)][[
        "location_name", "travel_limit_start_date", "travel_limit_end_date",
        "stay_home_start_date", "stay_home_end_date", "educational_fac_start_date",
        "educational_fac_end_date", "any_gathering_restrict_start_date",
        "any_gathering_restrict_end_date", "any_business_start_date", "any_business_end_date",
        "all_non-ess_business_start_date", "all_non-ess_business_end_date"
    ]]
    dict_state_to_policy_dates = {}
    for location in df.location_name.unique():
        df_temp = df[df.location_name == location].reset_index(drop=True)
        dict_state_to_policy_dates[location] = {
            policy: [df_temp.loc[0, f"{policy}_start_date"], df_temp.loc[0, f"{policy}_end_date"]]
            for policy in policies
        }
    check_us_policy_data_consistency(policies=policies, df_policy_raw_us=df)
    df_policies_US = create_features_from_ihme_dates(
        df_policy_raw_us=df,
        dict_state_to_policy_dates=dict_state_to_policy_dates,
        policies=policies,
    )
    df_policies_US_final = create_final_policy_features_us(df_policies_US=df_policies_US)
    return df_policies_US_final


def read_measures_oxford_data(yesterday: str):
    measures = pd.read_csv('https://github.com/OxCGRT/covid-policy-tracker/raw/master/data/OxCGRT_latest.csv')
    filtr = ['CountryName', 'CountryCode', 'Date']
    target = ['ConfirmedCases', 'ConfirmedDeaths']
    msr = [
        'C1_School closing', 'C2_Workplace closing', 'C3_Cancel public events', 'C4_Restrictions on gatherings',
        'C5_Close public transport', 'C6_Stay at home requirements', 'C7_Restrictions on internal movement',
        'C8_International travel controls', 'H1_Public information campaigns'
    ]

    flags = ['C' + str(i) + '_Flag' for i in range(1, 8)] + ["H1_Flag"]
    measures = measures.loc[:, filtr + msr + flags + target]
    measures['Date'] = measures['Date'].apply(lambda x: datetime.strptime(str(x), '%Y%m%d'))
    for col in target:
        #measures[col] = measures[col].fillna(0)
        measures[col] = measures.groupby('CountryName')[col].ffill()
        

    measures['C1_Flag'] = [0 if x <= 0  else y for (x,y) in zip(measures['C1_School closing'],measures['C1_Flag'])]
    measures['C2_Flag'] = [0 if x <= 0  else y for (x,y) in zip(measures['C2_Workplace closing'],measures['C2_Flag'])]
    measures['C3_Flag'] = [0 if x <= 0  else y for (x,y) in zip(measures['C3_Cancel public events'],measures['C3_Flag'])]
    measures['C4_Flag'] = [0 if x <= 0  else y for (x,y) in zip(measures['C4_Restrictions on gatherings'],measures['C4_Flag'])]
    measures['C5_Flag'] = [0 if x <= 0  else y for (x,y) in zip(measures['C5_Close public transport'],measures['C5_Flag'])]
    measures['C6_Flag'] = [0 if x <= 0  else y for (x,y) in zip(measures['C6_Stay at home requirements'],measures['C6_Flag'])]
    measures['C7_Flag'] = [0 if x <= 0  else y for (x,y) in zip(measures['C7_Restrictions on internal movement'],measures['C7_Flag'])]
    measures['H1_Flag'] = [0 if x <= 0  else y for (x,y) in zip(measures['H1_Public information campaigns'],measures['H1_Flag'])]

    measures['C1_School closing'] = [int(a and b) for a, b in zip(measures['C1_School closing'] >= 2, measures['C1_Flag'] == 1)]

    measures['C2_Workplace closing'] = [int(a and b) for a, b in zip(measures['C2_Workplace closing'] >= 2, measures['C2_Flag'] == 1)]

    measures['C3_Cancel public events'] = [int(a and b) for a, b in zip(measures['C3_Cancel public events'] >= 2, measures['C3_Flag'] == 1)]

    measures['C4_Restrictions on gatherings'] = [int(a and b) for a, b in zip(measures['C4_Restrictions on gatherings'] >= 1, measures['C4_Flag'] == 1)]

    measures['C5_Close public transport'] = [int(a and b) for a, b in zip(measures['C5_Close public transport'] >= 2, measures['C5_Flag'] == 1)]

    measures['C6_Stay at home requirements'] = [int(a and b) for a, b in zip(measures['C6_Stay at home requirements'] >= 2, measures['C6_Flag'] == 1)]

    measures['C7_Restrictions on internal movement'] = [int(a and b) for a, b in zip(measures['C7_Restrictions on internal movement'] >= 2, measures['C7_Flag'] == 1)]

    measures['C8_International travel controls'] = [int(a) for a in (measures['C8_International travel controls'] >= 3)]

    measures['H1_Public information campaigns'] = [int(a and b) for a, b in zip(measures['H1_Public information campaigns'] >= 1, measures['H1_Flag'] == 1)]


    #measures = measures.loc[:, measures.isnull().mean() < 0.1]
    msr = set(measures.columns).intersection(set(msr))

    #measures = measures.fillna(0)
    measures = measures.dropna()
    for col in msr:
        measures[col] = measures[col].apply(lambda x: int(x > 0))
    measures = measures[
        ['CountryName', 'Date'] + list(sorted(msr))
    ]
    measures["CountryName"] = measures.CountryName.replace({
        "United States": "US", "South Korea": "Korea, South", "Democratic Republic of Congo": "Congo (Kinshasa)",
        "Czech Republic": "Czechia", "Slovak Republic": "Slovakia",
    })

    measures = measures.fillna(0)
    msr = future_policies

    measures['Restrict_Mass_Gatherings'] = [
        int(a or b or c) for a, b, c in zip(
            measures['C3_Cancel public events'],
            measures['C4_Restrictions on gatherings'],
            measures['C5_Close public transport']
        )
    ]
    measures['Others'] = [
        int(a or b or c) for a, b, c in zip(
            measures['C2_Workplace closing'],
            measures['C7_Restrictions on internal movement'],
            measures['C8_International travel controls']
        )
    ]

    del measures['C2_Workplace closing']
    del measures['C3_Cancel public events']
    del measures['C4_Restrictions on gatherings']
    del measures['C5_Close public transport']
    del measures['C7_Restrictions on internal movement']
    del measures['C8_International travel controls']

    output = deepcopy(measures)
    output[msr[0]] = (measures.iloc[:, 2:].sum(axis=1) == 0).apply(lambda x: int(x))
    output[msr[1]] = [
        int(a and b) for a, b in zip(
            measures.iloc[:, 2:].sum(axis=1) == 1,
            measures['Restrict_Mass_Gatherings'] == 1
        )
    ]
    output[msr[2]] = [
        int(a and b and c) for a, b, c in zip(
            measures.iloc[:, 2:].sum(axis=1) > 0,
            measures['Restrict_Mass_Gatherings'] == 0,
            measures['C6_Stay at home requirements'] == 0,
        )
    ]
    output[msr[3]] = [
        int(a and b and c)
        for a, b, c in zip(
            measures.iloc[:, 2:].sum(axis=1) == 2,
            measures['C1_School closing'] == 1,
            measures['Restrict_Mass_Gatherings'] == 1,
        )
    ]
    output[msr[4]] = [
        int(a and b and c and d) for a, b, c, d in zip(
            measures.iloc[:, 2:].sum(axis=1) > 1,
            measures['C1_School closing'] == 0,
            measures['Restrict_Mass_Gatherings'] == 1,
            measures['C6_Stay at home requirements'] == 0,
        )
    ]
    output[msr[5]] = [
        int(a and b and c and d) for a, b, c, d in zip(
            measures.iloc[:, 2:].sum(axis=1) > 2,
            measures['C1_School closing'] == 1,
            measures['Restrict_Mass_Gatherings'] == 1,
            measures['C6_Stay at home requirements'] == 0,
        )
    ]
    output[msr[6]] = (measures['C6_Stay at home requirements'] == 1).apply(lambda x: int(x))
    output.rename(columns={'CountryName': 'country', 'Date': 'date'}, inplace=True)
    output['province'] = "None"
    output = output.loc[:, ['country', 'province', 'date'] + msr]
    output = output[output.date <= yesterday].reset_index(drop=True)
    return output


def gamma_t(day, state, params_dic):
    dsd, median_day_of_action, rate_of_action = params_dic[state]
    t = (day - pd.to_datetime(dsd)).days
    gamma = (2 / np.pi) * np.arctan(-(t - median_day_of_action) / 20 * rate_of_action) + 1
    return gamma


def make_increasing(sequence):
    for i in range(len(sequence)):
        sequence[i] = max(sequence[i],sequence[max(i-1,0)])
    return sequence

def get_normalized_policy_shifts_and_current_policy_us_only(
        policy_data_us_only: pd.DataFrame,
        pastparameters: pd.DataFrame,
):
    dict_current_policy = {}
    policy_list = future_policies
    policy_data_us_only['province_cl'] = policy_data_us_only['province'].apply(
        lambda x: x.replace(',', '').strip().lower()
    )
    states_upper_set = set(policy_data_us_only['province'])
    for state in states_upper_set:
        dict_current_policy[("US", state)] = list(compress(
            policy_list,
            (policy_data_us_only.query('province == @state')[
                 policy_data_us_only.query('province == @state')["date"] == policy_data_us_only.date.max()
             ][policy_list] == 1).values.flatten().tolist()
        ))[0]
    states_set = set(policy_data_us_only['province_cl'])
    pastparameters_copy = deepcopy(pastparameters)
    pastparameters_copy['Province'] = pastparameters_copy['Province'].apply(
        lambda x: str(x).replace(',', '').strip().lower()
    )
    params_dic = {}
    for state in states_set:
        params_dic[state] = pastparameters_copy.query('Province == @state')[
            ['Data Start Date', 'Median Day of Action', 'Rate of Action']
        ].iloc[0]

    policy_data_us_only['Gamma'] = [
        gamma_t(day, state, params_dic) for day, state in
        zip(policy_data_us_only['date'], policy_data_us_only['province_cl'])
    ]
    n_measures = policy_data_us_only.iloc[:, 3: -2].shape[1]
    dict_normalized_policy_gamma = {
        policy_data_us_only.columns[3 + i]: policy_data_us_only[
                                                policy_data_us_only.iloc[:, 3 + i] == 1
                                            ].iloc[:, -1].mean()
        for i in range(n_measures)
    }
    normalize_val = dict_normalized_policy_gamma[policy_list[0]]
    for policy in dict_normalized_policy_gamma.keys():
        dict_normalized_policy_gamma[policy] = dict_normalized_policy_gamma[policy] / normalize_val

    return dict_normalized_policy_gamma, dict_current_policy


def get_normalized_policy_shifts_and_current_policy_all_countries(
        policy_data_countries: pd.DataFrame,
        pastparameters: pd.DataFrame,
):
    dict_current_policy = {}
    policy_list = future_policies
    policy_data_countries['country_cl'] = policy_data_countries['country'].apply(
        lambda x: x.replace(',', '').strip().lower()
    )
    pastparameters_copy = deepcopy(pastparameters)
    pastparameters_copy['Country'] = pastparameters_copy['Country'].apply(
        lambda x: str(x).replace(',', '').strip().lower()
    )
    params_countries = pastparameters_copy['Country']
    params_countries = set(params_countries)
    policy_data_countries_bis = policy_data_countries.query("country_cl in @params_countries")
    countries_upper_set = set(policy_data_countries[policy_data_countries.country != "US"]['country'])
    # countries_in_oxford_and_params = params_countries.intersection(countries_upper_set)
    for country in countries_upper_set:
        dict_current_policy[(country, "None")] = list(compress(
            policy_list,
            (policy_data_countries.query('country == @country')[
                 policy_data_countries.query('country == @country')["date"]
                 == policy_data_countries.query('country == @country').date.max()
             ][policy_list] == 1).values.flatten().tolist()
        ))[0]
    countries_common = sorted([x.lower() for x in countries_upper_set])
    pastparam_tuples_in_oxford = pastparameters_copy[
        (pastparameters_copy.Country.isin(countries_common)) &
        (pastparameters_copy.Province != "None")
    ].reset_index(drop=True)
    pastparam_tuples_in_oxford["tuple_name"] = list(zip(pastparam_tuples_in_oxford.Country,
                                                        pastparam_tuples_in_oxford.Province))
    for tuple in pastparam_tuples_in_oxford.tuple_name.unique():
        country, province = tuple
        country = country[0].upper() + country[1:]
        dict_current_policy[(country, province)] = dict_current_policy[(country, "None")]

    countries_set = set(policy_data_countries['country_cl'])

    params_dic = {}
    countries_set = countries_set.intersection(params_countries)
    for country in countries_set:
        params_dic[country] = pastparameters_copy.query('Country == @country')[
                ['Data Start Date', 'Median Day of Action', 'Rate of Action']
        ].iloc[0]

    policy_data_countries_bis['Gamma'] = [
        gamma_t(day, country, params_dic) for day, country in
        zip(policy_data_countries_bis['date'], policy_data_countries_bis['country_cl'])
    ]
    n_measures = policy_data_countries_bis.iloc[:, 3:-2].shape[1]
    dict_normalized_policy_gamma = {
        policy_data_countries_bis.columns[3 + i]: policy_data_countries_bis[
                                                      policy_data_countries_bis.iloc[:, 3 + i] == 1
                                                  ].iloc[:, -1].mean()
        for i in range(n_measures)
    }
    normalize_val = dict_normalized_policy_gamma[policy_list[0]]
    for policy in dict_normalized_policy_gamma.keys():
        dict_normalized_policy_gamma[policy] = dict_normalized_policy_gamma[policy] / normalize_val

    return dict_normalized_policy_gamma, dict_current_policy


def add_aggregations_backtest(df_backtest_performance: pd.DataFrame) -> pd.DataFrame:
    df_temp = df_backtest_performance.copy()
    df_temp_continent = df_temp.groupby("continent")[[
        "train_mape_cases", "train_mape_deaths", "train_mae_cases",
        "train_mae_deaths", "train_mse_cases", "train_mse_deaths",
        "test_mape_cases", "test_mape_deaths", "test_mae_cases",
        "test_mae_deaths", "test_mse_cases", "test_mse_deaths",
        "mape_daily_delta_cases", "mape_daily_delta_deaths",
    ]].mean().reset_index()
    df_temp_country = df_temp.groupby(["continent", "country"])[[
        "train_mape_cases", "train_mape_deaths", "train_mae_cases",
        "train_mae_deaths", "train_mse_cases", "train_mse_deaths",
        "test_mape_cases", "test_mape_deaths", "test_mae_cases",
        "test_mae_deaths", "test_mse_cases", "test_mse_deaths",
        "mape_daily_delta_cases", "mape_daily_delta_deaths",
    ]].mean().reset_index()
    columns_none = [
        "country", "province", "train_start_date", "train_end_date", "test_start_date", "test_end_date",
    ]
    columns_nan = [
        "train_sign_mpe_cases", "train_sign_mpe_deaths", "test_sign_mpe_cases", "test_sign_mpe_deaths",
    ]
    for col in columns_none:
        df_temp_continent[col] = "None"
    for col in columns_none[1:]:
        df_temp_country[col] = "None"
    for col in columns_nan:
        df_temp_continent[col] = np.nan
        df_temp_country[col] = np.nan

    all_columns = [
        "continent", "country", "province", "train_start_date", "train_end_date", "train_mape_cases",
        "train_mape_deaths", "train_sign_mpe_cases", "train_sign_mpe_deaths", "train_mae_cases", "train_mae_deaths",
        "train_mse_cases", "train_mse_deaths", "test_start_date", "test_end_date", "test_mape_cases",
        "test_mape_deaths", "test_sign_mpe_cases", "test_sign_mpe_deaths", "test_mae_cases", "test_mae_deaths",
        "test_mse_cases", "test_mse_deaths", "mape_daily_delta_cases", "mape_daily_delta_deaths",
    ]
    df_temp_continent = df_temp_continent[all_columns]
    df_temp_country = df_temp_country[all_columns]
    df_backtest_perf_final = pd.concat([df_backtest_performance, df_temp_continent, df_temp_country]).sort_values(
        ["continent", "country", "province"]
    ).reset_index(drop=True)
    for col in [
        "train_mape_cases", "train_mape_deaths", "train_mae_cases", "train_mae_deaths",
        "train_mse_cases", "train_mse_deaths", "test_mape_cases", "test_mape_deaths",
        "test_mae_cases", "test_mae_deaths", "test_mse_cases", "test_mse_deaths",
        "mape_daily_delta_cases", "mape_daily_delta_deaths",

    ]:
        df_backtest_perf_final[col] = df_backtest_perf_final[col].round(3)

    df_backtest_perf_final.drop_duplicates(subset=["continent", "country", "province"], inplace=True)
    df_backtest_perf_final.reset_index(drop=True, inplace=True)
    return df_backtest_perf_final


def get_testing_data_us() -> pd.DataFrame:
    """
    :return: a DataFrame where the column of interest is 'testing_cnt_daily'
    which gives the numbers of new daily tests per state
    """
    df_test = pd.read_csv("https://covidtracking.com/api/v1/states/daily.csv")
    df_test["country"] = "US"
    df_test["continent"] = "North America"
    df_test["province"] = df_test.state.map(MAPPING_STATE_CODE_TO_STATE_NAME)
    df_test.drop("state", axis=1, inplace=True)
    df_test["date"] = df_test.date.apply(lambda x: str(x)[:4] + "-" + str(x)[4:6] + "-" + str(x)[6:])
    df_test["date"] = pd.to_datetime(df_test.date)
    df_test = df_test.sort_values(["province", "date"]).reset_index(drop=True)
    df_test = df_test[[
        "continent", "country", "province", "date", "totalTestResults"
    ]]
    df_test.rename(columns={"totalTestResults": "testing_cnt"}, inplace=True)
    list_df_concat = []
    for state in df_test.province.unique():
        df_temp = df_test[df_test.province == state].reset_index(drop=True)
        df_temp["testing_cnt_shift"] = df_temp.testing_cnt.shift(1)
        df_temp["testing_cnt_daily"] = df_temp.testing_cnt - df_temp.testing_cnt_shift
        df_temp.loc[0, "testing_cnt_daily"] = df_temp.loc[0, "testing_cnt"]
        list_df_concat.append(df_temp)

    df_test_final = pd.concat(list_df_concat).reset_index(drop=True)
    df_test_final.drop(["testing_cnt", "testing_cnt_shift"], axis=1, inplace=True)
    return df_test_final

def create_df_policy_change_tracking():
    return ""

def upload_s3_file(file_name, object_name):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """
    bucket = 'itx-bhq-data-covidcollector'
    # If S3 object_name was not specified, use file_name
    object_name_folder = 'mit_pred/' + object_name

    # Upload the file
    extra_arg = {'ServerSideEncryption' : 'AES256'}
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket, object_name_folder,extra_arg)
    except ClientError as e:
        logging.error(e)
        return False
    return True



def getDaySince100(data):
    res = []
    count = -1
    for x in data['cumulative_cases']:
        if x >= 100 and count < 0:
            count = 0
        elif x >= 100 and count >= 0:
            count +=1
        else:
            count -=1
        res.append(count)
    resRev = []
    count = 0
    for x in reversed(res):
        if x>=0:
            resRev.insert(0,x)
        else:
            count -= 1
            resRev.insert(0,count)
    return resRev

def process_data(rawDF,provinceColumn, change_province_name, filename_input):
    if filename_input is not None:
        rawDF.to_csv( 'data_sandbox/raw_data_additional_states/'+filename_input, index=False)
    provinces = []
    populations = []
    Continents = []
    Countries = []
    population = pd.read_csv('data_sandbox/processed/Population_Global.csv')
    dictProv = {"KwaZulu-Natal": "KwaZulu_Natal",
                'St_Louis': 'St._Louis',
                'Mato Grosso': 'MatoGrosso',
                'Mato Grosso do Sul': 'MatoGrosso do Sul',
                'Northwest': 'North_West'}
    find_lastdate =  pd.DataFrame(data = {'last_date': [datetime(2020,11,13)], 'count': [1]})

    for country in rawDF.country.unique():
        #     if country not in ['Philippines', 'Ukraine']:
        countriesDF = rawDF[rawDF.country == country].reset_index(drop=True)
        country = 'US'  if country == 'USA' else country
        filename = country + '_J&J'
        for province in pd.unique(countriesDF[provinceColumn]):
            provinceDF = countriesDF[
                (countriesDF[provinceColumn] == province)].reset_index(drop=True)
            province = dictProv[province] if province in dictProv.keys() else province
            updatedData = pd.DataFrame([x for x in provinceDF.date], columns = ["date"])
            # print(country,province,updatedData.date.tail(1).values[0])
            find_lastdate = find_lastdate.append({'last_date':updatedData.date.tail(1).values[0], 'count':1 }, ignore_index=True)
            province_name = province.replace(' ', '_') if change_province_name == True else province

            updatedData['country'] = country
            updatedData['province'] = province_name
            updatedData['day_since100'] = getDaySince100(provinceDF)
            updatedData['case_cnt'] = provinceDF['cumulative_cases']
            updatedData['death_cnt'] = provinceDF['cumulative_deaths']
            for c in ['new_hospitalization', 'total_hospitalization','new_icu'
                ,'total_icu','new_recovered','total_recovered']:
                updatedData[c] = np.nan
            pathdr = 'data_sandbox/processed/'+filename.replace(' ', '_')
            try:
                os.mkdir(pathdr)
            except OSError:
                # print("")
                r=1
            updatedData.to_csv( pathdr +'/Cases_'+country.replace(' ', '_')+'_'+province.replace(' ', '_')+'.csv', index=False)
            # for population
            provinces.append(province_name)
            popul_column = 'population' if provinceColumn == "key" else provinceColumn+'_population'
            #             populations.append(provinceDF['population'][1])
            populations.append(provinceDF[popul_column][0])
            res_continent = population[(population.Country == country) & (population.Province == province_name)]
            if res_continent.shape[0] > 0:
                continent = res_continent.Continent.values[0]
            else:
                res_continent = population[(population.Country == country)]
                continent = res_continent.Continent.values[0]
                new_row = {'Continent':continent, 'Country':country, 'Province':province_name, 'pop2016':int(provinceDF[popul_column][0]) }
                population = population.append(new_row, ignore_index=True)
                population.to_csv('data_sandbox/processed/Population_Global.csv'  , index=False)
                print(f"new region: {continent} {country} {province_name} ")
            #                 continent = 0

            Continents.append(continent)
            Countries.append(country)

    updatedData = pd.DataFrame()
    updatedData['Continent']= Continents
    updatedData['Country'] = Countries
    updatedData['Province'] = provinces
    updatedData['pop2016'] = populations
    if provinceColumn == 'county':
        file_name = 'US_counties.csv'
    elif provinceColumn == 'state_province':
        file_name = 'Ex_US_regions.csv'
    else:
        file_name = 'deleteme_populations.csv'

    updatedData.to_csv( 'data_sandbox/processed/'+file_name, index=False)
    lastdate=pd.DataFrame(find_lastdate.groupby('last_date', as_index=False).sum()).sort_values(by='count',ascending=False,ignore_index=True)
    print(f"finished for {provinceColumn}")
    print(lastdate)
    return lastdate.last_date[0]


def runProcessData(date_files, logger, type_run):
    inputFile_us_county = "data_sandbox/raw_data_additional_states/" + date_files + "_county_data.csv"
    inputFile_us_ex_US = "data_sandbox/raw_data_additional_states/" + date_files + "_ex_us_regions.csv"
    if os.path.exists(inputFile_us_county):
        rawDF_us_county = pd.read_csv(inputFile_us_county)
        rawDF_us_county = rawDF_us_county.sort_values(['date']).reset_index(drop=True)
        last_date = process_data(rawDF_us_county,'county',True,None)
    elif os.path.exists(inputFile_us_ex_US):
        rawDF_ex_us_provinces = pd.read_csv(inputFile_us_ex_US)
        rawDF_ex_us_provinces = rawDF_ex_us_provinces.sort_values(['date']).reset_index(drop=True)
        last_date = process_data(rawDF_ex_us_provinces,'county',True,None)
    else:
        client = boto3.client('s3')
        file_path_bef = 'gt_for_mit/'
        if type_run == "US":
            file_path = f'{date_files}_county_data.csv'
            print(f"getting {file_path}")
            logger.info(f"getting {file_path}")
            obj = client.get_object(Bucket='itx-bhq-data-covidcollector', Key= file_path_bef + file_path)
            rawDF_us_county = pd.read_csv(obj['Body'])
            rawDF_us_county = rawDF_us_county.sort_values(['date']).reset_index(drop=True)
            last_date = process_data(rawDF_us_county,'county',True,file_path)
        elif type_run == "ExUS":
            file_path = f'{date_files}_ex_us_regions.csv'
            print(f"getting {file_path}")
            logger.info(f"getting {file_path}")
            obj = client.get_object(Bucket='itx-bhq-data-covidcollector', Key= file_path_bef + file_path)
            rawDF_ex_us_provinces = pd.read_csv(obj['Body'])
            rawDF_ex_us_provinces = rawDF_ex_us_provinces.sort_values(['date']).reset_index(drop=True)
            last_date = process_data(rawDF_ex_us_provinces,'state_province',False,file_path)

    return last_date

#runProcessData("100220")