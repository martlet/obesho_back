# -*- coding: utf-8 -*-

import sys

from obesho_back import (Session, Model, Size, AvailableSize, OrderStatus)


def main(_):
    models = [
        Model(id=1, name='Alpha', price=31, img='img/model/a.jpg'),
        Model(id=2, name='Bravo', price=32, img='img/model/b.jpg'),
        Model(id=3, name='Charlie', price=33, img='img/model/c.jpg'),
        Model(id=4, name='Delta', price=34, img='img/model/d.jpg'),
        Model(id=5, name='Echo', price=35, img='img/model/e.jpg'),
        Model(id=6, name='Foxtrot', price=36, img='img/model/f.jpg'),
        Model(id=7, name='Golf', price=37, img='img/model/g.jpg'),
        Model(id=8, name='Hotel', price=38, img='img/model/h.jpg'),
        Model(id=9, name='India', price=39, img='img/model/i.jpg'),
        Model(id=10, name='Juliett', price=40, img='img/model/j.jpg'),
    ]
    sizes = [Size(id=s) for s in range(35, 46)]
    available_sizes = []
    for m in models:
        for s in sizes:
            qty = 3 if s.id % 2 == 1 else 0
            a = AvailableSize(model_id=m.id, size_id=s.id, qty=qty)
            available_sizes.append(a)

    statuses = [
        OrderStatus(id=1, name='in_cart'),
        OrderStatus(id=2, name='paid'),
        OrderStatus(id=3, name='redeemed'),
    ]

    session = Session()
    for m in models:
        session.add(m)
    for s in sizes:
        session.add(s)
    for a in available_sizes:
        session.add(a)
    for s in statuses:
        session.add(s)
    session.commit()


if __name__ == '__main__':
    sys.exit(main(sys.argv[0:]))
