# -*- coding: utf-8 -*-

import sys
import logging

import simplejson as json

from sqlalchemy import (
        create_engine, orm,
        Column, Integer, Float, String, Sequence, DateTime, ForeignKey)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, subqueryload #, joinedload, contains_eager

import tornado.ioloop
import tornado.httputil
import tornado.web


__version__ = '0.1.0'

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.DEBUG)
log = logging.getLogger('obesho_back')

engine = create_engine('sqlite:///os.sqlite', echo=True)
Session = sessionmaker(bind=engine)
Base = declarative_base()

HTTPCode_OK = 200
HTTPCode_Created = 201
HTTPCode_BadRequest = 400
HTTPCode_Conflict = 409
HTTPCode_Gone = 410
HTTPCode_InternalServerError = 500


class Error(Exception):
    def __init__(self, message, http_code_hint=None):
        super(Error, self).__init__(message)
        if http_code_hint:
            self.http_code_hint = http_code_hint
        else:
            self.http_code_hint = HTTPCode_InternalServerError


class ValueError(Error):
    pass


class OperationError(Error):
    pass


def entity_as_dict(entity):
    return {
        column.name : getattr(entity, column.name)
        for column in entity.__table__.columns
    }


class Model(Base):
    # pylint: disable=no-init
    __tablename__ = 'model'

    id = Column(Integer, Sequence('model_id_seq'), primary_key=True)
    name = Column(String(200), unique=True, nullable=False)
    price = Column(Float(2, True), nullable=False)
    img = Column(String(1000), nullable=False)

    # TODO: Outstanding orders...
    #available_sizes = relationship("AvailableSize", backref='model',
    #    cascade="all, delete, delete-orphan")
    available_sizes = relationship("AvailableSize", backref='model')

    def rr(self):
        return {'id': self.id, 'name': self.name, 'price': self.price, 'img': self.img,
            'available_sizes': [
                {'size_id': o.size_id, 'qty': o.qty}
                for o in self.available_sizes
            ]}


class Size(Base):
    # pylint: disable=no-init
    __tablename__ = 'size'

    id = Column(Integer, Sequence('size_id_seq'), primary_key=True)

    # TODO: Outstanding orders...
    available_sizes = relationship("AvailableSize", backref='size',
        cascade="all, delete, delete-orphan")


class AvailableSize(Base):
    # pylint: disable=no-init
    __tablename__ = 'available_size'

    model_id = Column(Integer, ForeignKey('model.id'), primary_key=True)
    size_id = Column(Integer, ForeignKey('size.id'), primary_key=True)
    qty = Column(Integer, nullable=False)

    #model = relationship("Model")
    #size = relationship("Size")


class Order(Base):
    # pylint: disable=no-init
    __tablename__ = 'order'

    def __init__(self, id=None):
        self.id = id

    id = Column(Integer, Sequence('order_id_seq'), primary_key=True) # TODO: Integer is too simple.

    items = relationship('OrderItem')


class OrderItem(Base):
    # pylint: disable=no-init
    __tablename__ = 'order_item'

    order_id = Column(Integer, ForeignKey('order.id'), primary_key=True)
    model_id = Column(Integer, ForeignKey('model.id'), primary_key=True)
    size_id = Column(Integer, ForeignKey('size.id'), primary_key=True)
    qty = Column(Integer, nullable=False)

    order = relationship('Order', backref='order')
    model = relationship('Model', backref='model')
    size = relationship('Size', backref='size')


class OrderStatus(Base):
    # pylint: disable=no-init
    __tablename__ = 'status'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)


class OrderStatusHistory(Base):
    # pylint: disable=no-init
    __tablename__ = 'order_status_history'

    def __init__(self, order_id, status_id, timestamp):
        self.order_id = order_id
        self.status_id = status_id
        self.timestamp = timestamp

    order_id = Column(Integer, ForeignKey('order.id'), primary_key=True)
    status_id = Column(Integer, ForeignKey('status.id'), primary_key=True)
    timestamp = Column(DateTime, nullable=False)

    order = relationship("Order")
    status = relationship("OrderStatus")


class DataStore(object):
    def __init__(self):
        self.session = Session()

    def get_models_incl_available_sizes(self):
        return (self.session.query(Model)
                #.options(subqueryload(Model.available_sizes))
                .options(subqueryload(Model.available_sizes))
                #.options(joinedload(Model.available_sizes))
                .order_by(Model.id)
                .all())

    def get_sizes(self):
        return self.session.query(Size).order_by(Size.id).all()

    def start_new_order(self):
        order = Order()
        self.session.add(order)
        # TODO: Add entry for order status history.
        #self.session.commit()
        return order

    def get_order_by_id(self, id):
        order = (self.session.query(Order)
            .filter_by(id=id)
            .one())
        return order

    def add_item_to_order(self, order_id, model_id, size_id, qty):
        # NOTE: This operation could be a stored procedure in the DB and the
        # code here to be limited to its invokation. Alas, the used DBMS does
        # not support stored procedures.

        print("order_id: {0}".format(order_id))  # TODO: line: remove

        available_size = (self.session.query(AvailableSize)
            .filter_by(model_id=model_id)
            .filter_by(size_id=size_id)
            .one())
        if available_size.qty < qty:
            raise OperationError("The requested quantity is not available!",
                http_code_hint=HTTPCode_BadRequest)

        available_size.qty -= qty

        new_order_item = True

        if order_id is None:
            # Start new order.
            order = Order()
            self.session.add(order)
        else:
            try:
                order = self.get_order_by_id(order_id)
            except orm.exc.NoResultFound:
                raise tornado.web.HTTPError(400,
                    log_message="Attempt to add item to non-existing order!",
                    reason="The specified order does not exist!")

            # Obtain entry for order item (if it exists).
            try:
                order_item = (self.session.query(OrderItem)
                    .filter_by(order_id=order.id)
                    .filter_by(model_id=model_id)
                    .filter_by(size_id=size_id)
                    .one())
                order_item.qty += qty
                new_order_item = False
            except orm.exc.NoResultFound:
                pass

        if new_order_item:
            # Start new entry for order item.
            order_item = OrderItem(
                #order_id=order.id,
                model_id=model_id,
                size_id=size_id,
                qty=qty)
            order.items.append(order_item)
            #self.session.add(order_item)

        self.session.commit()
        # TODO: Add proper call to rollback()

        print("Modified Order with id: {0}".format(order.id))  # TODO: line: remove

        #return {
        #    'order': order,
        #    'order_item': order_item,
        #    'available_size': available_size
        #}
        return {
            'order': entity_as_dict(order),
            'order_item': entity_as_dict(order_item),
            'available_size': entity_as_dict(available_size),
        }


def custom_parse_body_arguments(content_type, body, arguments, files, headers=None):
    if content_type.startswith('application/json'):
        try:
            data = tornado.escape.json_decode(tornado.httputil.native_str(body))
        except Exception as e:
            tornado.httputil.gen_log.warning("Invalid json body: %s", e)
            data = {}
        for name, value in data.items():
            arguments.setdefault(name, [value])
    else:
        return orig_parse_body_arguments(content_type, body, arguments, files, headers)

orig_parse_body_arguments = tornado.httputil.parse_body_arguments
tornado.httputil.parse_body_arguments = custom_parse_body_arguments


def custom_json_encode(value):
    return json.dumps(value, use_decimal=True).replace("</", "<\\/")

from tornado import escape as _escape
orig_json_encode = _escape.json_encode
_escape.json_encode = custom_json_encode


class ApiHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.add_header('Access-Control-Allow-Origin', '*')
        self.add_header('Access-Control-Allow-Headers', 'Content-Type, x-xsrf-token')
        self.add_header('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE,OPTIONS,HEAD')
        #self.add_header('Access-Control-Allow-Credentials', 'true|false')
        #self.add_header('Access-Control-Max-Age', '86400')

    def decode_argument(self, value, name=None):
        try:
            return super(ApiHandler, self).decode_argument(value, name)
        except TypeError:
            content_type = self.request.headers.get('Content-Type', '')
            if content_type.startswith('application/json'):
                return value
            else:
                raise

    def write_error(self, status_code, **kwargs):
        if self.request.headers.get('Accept', '').startswith('application/json'):
            self.write({'status_code': status_code, 'message': self._reason})
            self.finish()
        else:
            super(ApiHandler, self).write_error(status_code, **kwargs)


class HomeHandler(ApiHandler):
    def get(self):
        self.write({'name': 'ObeSho API', 'version': __version__})


class VersionHandler(ApiHandler):
    def get(self):
        self.write({'version': __version__})


class CatalogHandler(ApiHandler):
    def prepare(self):
        # pylint: disable=attribute-defined-outside-init
        self.storage = DataStore()

    def get(self):
        models = self.storage.get_models_incl_available_sizes()
        sizes = self.storage.get_sizes()

        self.write({
            'models': [m.rr() for m in models],
            'sizes': [entity_as_dict(s) for s in sizes],
        })


class OrderItemHandler(ApiHandler):
    def prepare(self):
        # pylint: disable=attribute-defined-outside-init
        self.storage = DataStore()

    def post(self):
        order_id = self.get_argument('order_id', [], strip=False)
        model_id = self.get_argument('model_id', strip=False)
        size_id = self.get_argument('size_id', strip=False)
        qty = 1  # TODO: In the future this may be a parameter of the API call. ;)

        try:
            result = self.storage.add_item_to_order(order_id, model_id, size_id, qty)
        except Error as e:
            message = "Error adding item to order: {0}".format(e)
            raise tornado.web.HTTPError(e.http_code_hint, log_message=message, reason=message)

        # The storage (DB) method returns the modified entities and we may
        # choose whether to return all of them in the response or just the
        # specified resource.

        self.write(result)

    def options(self):
        self.set_header('Allow', 'POST,DELETE')


def main(_):
    application = tornado.web.Application([
        (r"/catalog/?", CatalogHandler),
        (r"/orderitem/", OrderItemHandler),
        (r"/version/", VersionHandler),
        (r"/", HomeHandler),
    ])

    application.listen(17489)
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        tornado.ioloop.IOLoop.instance().stop()


if __name__ == '__main__':
    sys.exit(main(sys.argv[0:]))
