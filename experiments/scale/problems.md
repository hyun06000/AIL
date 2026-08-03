P1: Fetch JSON from a URL with a 5 second timeout. Retry up to 3 times with exponential backoff. On success return an object with ok, name, email taken from the JSON. On failure return ok false and the error message.
P2: Given CSV text with columns name,dept,salary, compute the average salary per dept. Skip malformed rows and count them. Return the averages and the skipped count.
P3: Process a list of jobs with an operation budget of 10 operations. Stop when the budget is exhausted. Collect failed jobs. Return counts of done, failed, remaining.
P4: Merge two already-sorted lists of numbers into one sorted list without using a built-in sort. Return the merged list and its length.
P5: Given a text, count word frequencies (case-insensitive, split on whitespace) and return the top 3 most frequent words with their counts.
P6: Validate a config object: it must have a name (non-empty string), a port (number 1-65535), and a mode that is either "dev" or "prod". Return a list of validation error messages, empty if valid.
P7: Given a list of lists of numbers, return the total sum, the count of numbers, and the largest single number seen.
P8: Given a list of user records with fields name, age, active, return only the active users aged 18 or over, as a list of objects with name and an isAdult flag.
P9: Send an HTTP POST for each item in a list, at most 5 requests total (budget). Collect ids from successful responses and error messages from failures. Return both lists.
P10: Parse a URL query string like "a=1&b=hello&c=" into an object of key-value pairs, counting how many values were empty. Return the object and the empty count.
