from typing import *
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import recall_score, precision_score, accuracy_score
import pandas as pd
import sqlite3
from pathlib import Path
import pm4py
from pm4py.objects.log.importer.xes import importer as xes_importer
from pm4py.algo.discovery.alpha import algorithm as alpha_miner


# Enhance dataframe with start and end activities
def getActivityByOrderingTimestamp(con, caseId, order: str) -> Optional[str]:
    cursor = con.cursor()
    cursor.execute(f"select ACTIVITY_EN from Pizza_Event where _case_key = ? order by eventtime {order} limit 1", (caseId, ))
    res = cursor.fetchone()
    cursor.close()
    if len(res) == 0:
        return None
    return res[0]


def getStartActivity(con, caseId) -> Optional[str]:
    return getActivityByOrderingTimestamp(con, caseId, "asc")


def getEndActivity(con, caseId) -> Optional[str]:
    return getActivityByOrderingTimestamp(con, caseId, "desc")


def algo(df, column: str):
    df = df.copy()
    X = df.drop([column], axis=1)
    y = df[column]


    # Split the data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train a decision tree classifier on the training data
    clf = RandomForestClassifier(random_state=42) # Going with RandomForest because it is 0.3324 accurate (DecisionTree is 0.24)
    clf.fit(X_train, y_train)

    # Evaluate the performance of the classifier on the testing data
    score = clf.score(X_test, y_test)

    # recall
    y_pred = clf.predict(X_test)
    recall = recall_score(y_test, y_pred, average='macro')

    # precision
    precision = precision_score(y_test, y_pred, average='macro')


    print()
    # Print the feature importances
    importances = clf.feature_importances_
    featureImportances = []
    for feature, importance in zip(X.columns, importances):
        featureImportances.append({"feature": feature, "importance": importance})
    return {
        "accuracy": score,
        "recall": recall,
        "precision": precision,
        "column": column,
        "feature_importances": featureImportances,
    }


def algoPrinter(algoResult: Dict):
    print("===")
    print(f"Accuracy: {algoResult['accuracy']}")
    print(f"Recall: {algoResult['recall']}")
    print(f"Precision: {algoResult['precision']}")
    print("----")
    print(f"Column: {algoResult['column']}")
    print("----")
    print("Feature Importances:")
    for i in algoResult["feature_importances"]:
        print(f"{i['feature']}: {i['importance']}")
    print("===")
    print()



def prepareData(con, df: pd.DataFrame) -> pd.DataFrame:
    df.drop("Customer_ID", axis=1, inplace=True)

    df = pd.get_dummies(df, columns=["CustomerType", "CustomerLocation", "DistributionChannel", "Weekday", "CostFactor", "PizzaSize", "PizzaType"])
    df = pd.get_dummies(df, columns=["Variant"])

    df["Profit"] = df["Revenue"] - df["Costs"]
    df["IsOrderProfitable"] = df["Profit"] > 0

    # Drop Revenue and Costs because that would train the model to give us a non useful result
    dfPredictPrfitablity = df.copy()
    dfPredictPrfitablity.drop("Profit", axis=1, inplace=True)
    dfPredictPrfitablity.drop("Costs", axis=1, inplace=True)
    dfPredictPrfitablity.drop("Revenue", axis=1, inplace=True)
    algo(dfPredictPrfitablity, "IsOrderProfitable")

    dfPredictCustomerSatisfaction = df.copy()
    dfPredictCustomerSatisfaction["IsCustomerSatisfied"] = dfPredictCustomerSatisfaction["CustomerSatisfaction"] >= 3
    algo(dfPredictCustomerSatisfaction, "CustomerSatisfaction")

    log = xes_importer.apply("../data/Pizza_Event.xes")
    net, initial_marking, final_marking = alpha_miner.apply(log)

    process_model = pm4py.discover_bpmn_inductive(log)
    # pm4py.view_bpmn(process_model)

    pm4py.stats.get_case_duration(log, case_id="895")

    df["Duration"] = df["_CASE_KEY"].map(lambda x: pm4py.stats.get_case_duration(log, case_id=str(x)))
    df["StartActivity"] = df["_CASE_KEY"].map(lambda caseId : getStartActivity(con, caseId))
    df["EndActivity"] = df["_CASE_KEY"].map(lambda caseId : getEndActivity(con, caseId))
    df.drop("_CASE_KEY", axis=1, inplace=True)

    # convert startactity with one hot encoding
    df = pd.get_dummies(df, columns=["StartActivity"])
    df = pd.get_dummies(df, columns=["EndActivity"])
    return df


def predictProfitabilityAndCustomerSatisfactionBasedOnSQLQuery(con, sql: str) -> Dict:
    df = pd.read_sql(sql, con)
    df = prepareData(con, df)
    # Drop Revenue and Costs because that would train the model to give us a non useful result
    dfPredictPrfitablity = df.copy()

    dfPredictPrfitablity.drop("Profit", axis=1, inplace=True)
    dfPredictPrfitablity.drop("Costs", axis=1, inplace=True)
    dfPredictPrfitablity.drop("Revenue", axis=1, inplace=True)
    proitability = algo(dfPredictPrfitablity, "IsOrderProfitable")

    dfPredictCustomerSatisfaction = df.copy()
    dfPredictCustomerSatisfaction["IsCustomerSatisfied"] = dfPredictCustomerSatisfaction["CustomerSatisfaction"] >= 3
    satisfaction = algo(dfPredictCustomerSatisfaction, "CustomerSatisfaction")
    return {
        "profitability": proitability,
        "satisfaction": satisfaction,
    }


if __name__ == "__main__":
    path = Path("../data/data.sqlite")
    if not path.exists():
        # Prevent creating an empty db
        raise Exception("Database does not exist")
    _con = sqlite3.connect(path)
    res = predictProfitabilityAndCustomerSatisfactionBasedOnSQLQuery(_con, "SELECT * FROM Pizza_Case WHERE Variant != 5")
    for i in res:
        algoPrinter(res[i])
        print()
        print()

