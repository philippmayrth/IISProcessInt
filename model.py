# %%
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import recall_score, precision_score, accuracy_score
import pandas as pd
import sqlite3
from pathlib import Path


# %%
dbPath = Path("../data/data.sqlite")
if not dbPath.exists():
    # Avoid creating an empty database
    raise Exception("Database file does not exist")
con = sqlite3.connect(dbPath)

# %%
customerTypeMap = ["Student", "Teenager", "Adult", "Senior"]
customerLocationMap = ["Munich District One","Munich District Three","Munich District Two","Munich District Four","Munich District Five"]
distributionChannelMap =  ["Feedera SE", "Deliver Now Holding", "Deliveruu Inc.", "Orderly SE", "BestOrder Inc.", "TownExpress Inc.", "Heropizza Lmtd."]
weekdayMap = ["Sunday", "Tuesday", "Friday", "Saturday", "Wednesday", "Monday", "Thursday"]
costfactorMap = ["","Chef 2","Chef 1","Ingredients","Delivery Scooters","Phone Bill","Delivery Guy 2","Distribution channel fees","Waiter","Delivery Guy 1"]
sizeMap = ["Medium", "Small", "Large"]
typeMap = ["Funghi", "Salami", "Calzone", "Speciale", "Magherita", "Paprika", "Veggie"]

# %%
df = pd.read_sql("SELECT * FROM Pizza_Case WHERE Variant != 5", con)
# df.drop(["_CASE_KEY"], axis=1, inplace=True)
df.drop("Customer_ID", axis=1, inplace=True)

# df["CustomerType"] = df["CustomerType"].map(customerTypeMap.index)
# df["CustomerLocation"] = df["CustomerLocation"].map(customerLocationMap.index)
# df["DistributionChannel"] = df["DistributionChannel"].map(distributionChannelMap.index)
# df["Weekday"] = df["Weekday"].map(weekdayMap.index)
# df["CostFactor"] = df["CostFactor"].map(costfactorMap.index)
# df["PizzaSize"] = df["PizzaSize"].map(sizeMap.index)
# df["PizzaType"] = df["PizzaType"].map(typeMap.index)

df = pd.get_dummies(df, columns=["CustomerType", "CustomerLocation", "DistributionChannel", "Weekday", "CostFactor", "PizzaSize", "PizzaType"])
df = pd.get_dummies(df, columns=["Variant"])

df["Profit"] = df["Revenue"] - df["Costs"]
df["IsOrderProfitable"] = df["Profit"] > 0

df

# %%
# Extract the features and target variable
# X = df.drop(['CustomerSatisfaction'], axis=1)
# y = df['CustomerSatisfaction']

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
    print('Accuracy:', score)
    # recall

    y_pred = clf.predict(X_test)
    recall = recall_score(y_test, y_pred, average='macro')
    print('Recall:', recall)

    # precision
    precision = precision_score(y_test, y_pred, average='macro')
    print('Precision:', precision)


    print()
    # Print the feature importances
    importances = clf.feature_importances_
    for feature, importance in zip(X.columns, importances):
        print(feature, importance)

# %%
algo(df, "CustomerSatisfaction")

# %%
algo(df, "Profit")

# %%
# Drop Revenue and Costs because that would train the model to give us a non useful result
dfPredictPrfitablity = df.copy()
dfPredictPrfitablity.drop("Profit", axis=1, inplace=True)
dfPredictPrfitablity.drop("Costs", axis=1, inplace=True)
dfPredictPrfitablity.drop("Revenue", axis=1, inplace=True)
algo(dfPredictPrfitablity, "IsOrderProfitable")

# %%
dfPredictCustomerSatisfaction = df.copy()
dfPredictCustomerSatisfaction["IsCustomerSatisfied"] = dfPredictCustomerSatisfaction["CustomerSatisfaction"] >= 3
algo(dfPredictCustomerSatisfaction, "CustomerSatisfaction")

# %%
import pm4py
from pm4py.objects.log.importer.xes import importer as xes_importer
from pm4py.algo.discovery.alpha import algorithm as alpha_miner



# %%
log = xes_importer.apply("../data/Pizza_Event.xes")

# %%
log

# %%
net, initial_marking, final_marking = alpha_miner.apply(log)

# %%
process_model = pm4py.discover_bpmn_inductive(log)
pm4py.view_bpmn(process_model)

# %%
pm4py.stats.get_case_duration(log, case_id="895")

# %%
df

# %%
from typing import *
# Enhance dataframe with start and end activities
def getActivityByOrderingTimestamp(caseId, order: str) -> Optional[str]:
    cursor = con.cursor()
    cursor.execute(f"select ACTIVITY_EN from Pizza_Event where _case_key = ? order by eventtime {order} limit 1", (caseId, ))
    res = cursor.fetchone()
    cursor.close()
    if len(res) == 0:
        return None
    return res[0]

def getStartActivity(caseId) -> Optional[str]:
    return getActivityByOrderingTimestamp(caseId, "asc")

def getEndActivity(caseId) -> Optional[str]:
    return getActivityByOrderingTimestamp(caseId, "desc")


# %%
# Drop all cases of variant 5 because they are not in the log
#df = df[df["Variant"] != 5]


df["Duration"] = df["_CASE_KEY"].map(lambda x: pm4py.stats.get_case_duration(log, case_id=str(x)))
df["StartActivity"] = df["_CASE_KEY"].map(getStartActivity)
df["EndActivity"] = df["_CASE_KEY"].map(getEndActivity)
df.drop("_CASE_KEY", axis=1, inplace=True)
df

# %%
# convert startactity with one hot encoding
df = pd.get_dummies(df, columns=["StartActivity"])
df = pd.get_dummies(df, columns=["EndActivity"])

# %%
# Drop Revenue and Costs because that would train the model to give us a non useful result
dfPredictPrfitablity = df.copy()

dfPredictPrfitablity.drop("Profit", axis=1, inplace=True)
dfPredictPrfitablity.drop("Costs", axis=1, inplace=True)
dfPredictPrfitablity.drop("Revenue", axis=1, inplace=True)
algo(dfPredictPrfitablity, "IsOrderProfitable")

# %%
dfPredictCustomerSatisfaction = df.copy()
dfPredictCustomerSatisfaction["IsCustomerSatisfied"] = dfPredictCustomerSatisfaction["CustomerSatisfaction"] >= 3
algo(dfPredictCustomerSatisfaction, "CustomerSatisfaction")

# %%



