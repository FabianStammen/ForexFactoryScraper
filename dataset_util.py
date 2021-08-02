"""Dataset Util
A script that checks for Non-Economic duplicates in the dataset
"""
import csv

if __name__ == '__main__':
    count = dict()
    lockAt = list()
    with open('forex_factory_catalog.csv', mode='r') as file:
        reader = csv.reader(file, delimiter=',')
        for row in reader:
            if row[2] != 'Non-Economic':

                if row[0] not in count:
                    count[row[0]] = {row[3]: {row[1]: 0}}
                elif row[3] not in count[row[0]]:
                    count[row[0]][row[3]] = {row[1]: 0}
                elif row[1] not in count[row[0]][row[3]]:
                    count[row[0]][row[3]][row[1]] = 0
                else:
                    lockAt.append(row)
                count[row[0]][row[3]][row[1]] = count[row[0]][row[3]][row[1]] + 1

    # od = OrderedDict(sorted(count.items(), key=lambda x:x[1], reverse=True))
    for i, problem in enumerate(lockAt):
        print(str(i) + ': ' + str(problem) + ' : ' + str(count[problem[0]][problem[3]][problem[1]]))
