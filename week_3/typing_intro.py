from typing import List, Dict, TypedDict, Union


def greet(name: str) -> int:
    return name


numbers: List[int | str | bool] = [1, 2, 3, 4, "James", False]
numbers2: list[int | str] = [1, 2, 3, 4]

user: Dict[str, str | int] = {"name": "James", "age": 26}


class AgentData(TypedDict):
    name: str
    age: int
    is_student: bool


if __name__ == "__main__":
    print(greet("James"))
    print(greet(68))

    result = greet(57)
    print(type(result))

    print(f"Name: {user['name']}")
    print(f"Age: {user['age']}")
    print(f"Age: {user.get('age', 34)}")

    print(type(user))

    user2: AgentData = AgentData(name="Gabriel", age=20, is_student=True)

    user3: AgentData = {
        "name": "James",

    }

    value: Union[int | str] = "48"

    print(value)
    print(type(value))

    value: Union[int | str] = False

    print(value)
    print(type(value))

    add = lambda x,y: x+y
    print(add(3,5))
