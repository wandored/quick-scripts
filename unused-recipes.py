import pandas as pd




# read ingredients.csv into a DataFrame
ingredients = pd.read_csv('/tmp/ingredients.csv', usecols=['Item', 'Recipe'])

# read recipes.csv into a DataFrame
recipes = pd.read_csv('/tmp/recipe.csv', usecols=['Name', 'Recipe'])

# merge the ingredients and recipes DataFrames on 'Recipe'
df = pd.merge(recipes, ingredients, on='Recipe', how='right')

# df_del = all rows with NaN in 'Name'
df_del = df[df['Name'].isnull()]

# drop all rows where Item begins with 'BEEF'
df_del = df_del[df_del['Item'].str.startswith('BEEF')]
print(df_del)

# del_list = unique values in 'Recipe' column of df_del
del_list = df_del['Recipe'].unique()

print(len(del_list))
# print del_list to csv
with open('/tmp/unused-recipes.csv', 'w') as f:
    for item in del_list:
        f.write("%s\n" % item)
